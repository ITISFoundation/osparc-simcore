# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import functools
import random
from collections.abc import AsyncIterable, AsyncIterator
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime, timezone
from http import HTTPStatus
from itertools import repeat
from typing import Any
from unittest.mock import MagicMock, Mock

import aiopg.sa
import pytest
import redis.asyncio as aioredis
from aiohttp.test_utils import TestClient
from aiopg.sa.connection import SAConnection
from models_library.generics import Envelope
from psycopg2 import OperationalError
from pydantic import parse_obj_as
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.utils_login import UserInfoDict
from servicelib.aiohttp import status
from servicelib.rest_constants import RESPONSE_MODEL_POLICY
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.redis import get_redis_user_notifications_client
from simcore_service_webserver.users._notifications import (
    MAX_NOTIFICATIONS_FOR_USER_TO_KEEP,
    MAX_NOTIFICATIONS_FOR_USER_TO_SHOW,
    NotificationCategory,
    UserNotification,
    UserNotificationCreate,
    get_notification_key,
)
from simcore_service_webserver.users._notifications_handlers import (
    _get_user_notifications,
)
from simcore_service_webserver.users._preferences_api import (
    get_frontend_user_preferences_aggregation,
)
from simcore_service_webserver.users.schemas import PermissionGet, ProfileGet


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    # disables GC and DB-listener
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
            "WEBSERVER_DB_LISTENER": "0",
        },
    )


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_200_OK),
        (UserRole.USER, status.HTTP_200_OK),
        (UserRole.TESTER, status.HTTP_200_OK),
    ],
)
async def test_get_profile(
    logged_user: UserInfoDict,
    client: TestClient,
    user_role: UserRole,
    expected: HTTPStatus,
    primary_group: dict[str, Any],
    standard_groups: list[dict[str, Any]],
    all_group: dict[str, str],
):
    assert client.app

    url = client.app.router["get_my_profile"].url_for()
    assert url.path == "/v0/me"

    resp = await client.get(url.path)
    data, error = await assert_status(resp, expected)

    # check enveloped
    e = Envelope[ProfileGet].parse_obj(await resp.json())
    assert e.error == error
    assert e.data.dict(**RESPONSE_MODEL_POLICY) == data if e.data else e.data == data

    if not error:
        profile = ProfileGet.parse_obj(data)

        # TODO: fixture?
        product_group = {
            "accessRights": {"delete": False, "read": False, "write": False},
            "description": "osparc product group",
            "gid": 2,
            "inclusionRules": {},
            "label": "osparc",
            "thumbnail": None,
        }

        assert profile.login == logged_user["email"]
        assert profile.gravatar_id
        assert profile.first_name == logged_user.get("first_name", None)
        assert profile.last_name == logged_user.get("last_name", None)
        assert profile.role == user_role.name
        assert profile.groups

        got_profile_groups = profile.groups.dict(**RESPONSE_MODEL_POLICY)
        assert got_profile_groups["me"] == primary_group
        assert got_profile_groups["all"] == all_group

        sorted_by_group_id = functools.partial(sorted, key=lambda d: d["gid"])
        assert sorted_by_group_id(
            got_profile_groups["organizations"]
        ) == sorted_by_group_id([*standard_groups, product_group])

        assert profile.preferences == await get_frontend_user_preferences_aggregation(
            client.app, user_id=logged_user["id"], product_name="osparc"
        )


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_403_FORBIDDEN),
        (UserRole.USER, status.HTTP_204_NO_CONTENT),
        (UserRole.TESTER, status.HTTP_204_NO_CONTENT),
    ],
)
async def test_update_profile(
    logged_user: UserInfoDict,
    client: TestClient,
    user_role: UserRole,
    expected: HTTPStatus,
):
    assert client.app

    url = f"{client.app.router['update_my_profile'].url_for()}"
    assert str(url) == "/v0/me"

    resp = await client.put(url, json={"last_name": "Foo"})
    _, error = await assert_status(resp, expected)

    if not error:
        resp = await client.get(url)
        data, _ = await assert_status(resp, status.HTTP_200_OK)

        assert data["first_name"] == logged_user.get("first_name")
        assert data["last_name"] == "Foo"
        assert data["role"] == user_role.name


@pytest.fixture
def mock_failing_database_connection(mocker: Mock) -> MagicMock:
    """
    async with engine.acquire() as conn:
        await conn.execute(query)  --> will raise OperationalError
    """
    # See http://initd.org/psycopg/docs/module.html
    conn_execute = mocker.patch.object(SAConnection, "execute")
    conn_execute.side_effect = OperationalError(
        "MOCK: server closed the connection unexpectedly"
    )
    return conn_execute


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.USER, status.HTTP_503_SERVICE_UNAVAILABLE),
    ],
)
async def test_get_profile_with_failing_db_connection(
    logged_user: UserInfoDict,
    client: TestClient,
    mock_failing_database_connection: MagicMock,
    expected: HTTPStatus,
):
    """
    Reproduces issue https://github.com/ITISFoundation/osparc-simcore/pull/1160

    A logged user fails to get profie because though authentication because

    i.e. conn.execute(query) will raise psycopg2.OperationalError: server closed the connection unexpectedly

    SEE:
    - https://github.com/ITISFoundation/osparc-simcore/issues/880
    - https://github.com/ITISFoundation/osparc-simcore/pull/1160
    """
    assert client.app

    url = client.app.router["get_my_profile"].url_for()
    assert str(url) == "/v0/me"

    resp = await client.get(url.path)

    await assert_status(resp, expected)


@pytest.fixture
async def notification_redis_client(
    client: TestClient,
) -> AsyncIterable[aioredis.Redis]:
    assert client.app
    redis_client = get_redis_user_notifications_client(client.app)
    yield redis_client
    await redis_client.flushall()


@asynccontextmanager
async def _create_notifications(
    redis_client: aioredis.Redis, logged_user: UserInfoDict, count: int
) -> AsyncIterator[list[UserNotification]]:
    user_id = logged_user["id"]
    notification_categories = tuple(NotificationCategory)

    user_notifications: list[UserNotification] = [
        UserNotification.create_from_request_data(
            UserNotificationCreate.parse_obj(
                {
                    "user_id": user_id,
                    "category": random.choice(notification_categories),
                    "actionable_path": "a/path",
                    "title": "test_title",
                    "text": "text_text",
                    "date": datetime.now(timezone.utc).isoformat(),
                }
            )
        )
        for _ in range(count)
    ]

    redis_key = get_notification_key(user_id)
    if user_notifications:
        for notification in user_notifications:
            await redis_client.lpush(redis_key, notification.json())

    yield user_notifications

    await redis_client.flushall()


@pytest.mark.parametrize(
    "user_role,expected_response",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_200_OK),
        (UserRole.USER, status.HTTP_200_OK),
        (UserRole.TESTER, status.HTTP_200_OK),
    ],
)
@pytest.mark.parametrize(
    "notification_count",
    [
        0,
        MAX_NOTIFICATIONS_FOR_USER_TO_SHOW - 1,
        MAX_NOTIFICATIONS_FOR_USER_TO_SHOW,
        MAX_NOTIFICATIONS_FOR_USER_TO_SHOW + 1,
    ],
)
async def test_list_user_notifications(
    logged_user: UserInfoDict,
    notification_redis_client: aioredis.Redis,
    client: TestClient,
    notification_count: int,
    expected_response: HTTPStatus,
):
    assert client.app
    url = client.app.router["list_user_notifications"].url_for()
    assert str(url) == "/v0/me/notifications"
    response = await client.get(url.path)
    data, error = await assert_status(response, expected_response)
    if data:
        assert data == []
        assert not error

        async with _create_notifications(
            notification_redis_client, logged_user, notification_count
        ) as created_notifications:
            response = await client.get(url.path)
            json_response = await response.json()

            result = parse_obj_as(list[UserNotification], json_response["data"])
            assert len(result) <= MAX_NOTIFICATIONS_FOR_USER_TO_SHOW
            assert result == list(
                reversed(created_notifications[:MAX_NOTIFICATIONS_FOR_USER_TO_SHOW])
            )


@pytest.mark.parametrize(
    "user_role,expected_response",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_403_FORBIDDEN),
        (UserRole.USER, status.HTTP_204_NO_CONTENT),
        (UserRole.TESTER, status.HTTP_204_NO_CONTENT),
    ],
)
@pytest.mark.parametrize(
    "notification_dict",
    [
        pytest.param(
            {
                "user_id": "1",
                "category": NotificationCategory.NEW_ORGANIZATION,
                "actionable_path": "organization/40",
                "title": "New organization",
                "text": "You're now member of a new Organization",
                "date": "2023-02-23T16:23:13.122Z",
            },
            id="with_expected_data",
        ),
        pytest.param(
            {
                "id": "34116563-fb11-4365-9aec-7e44a3f296aa",
                "user_id": 1,
                "category": NotificationCategory.NEW_ORGANIZATION,
                "actionable_path": "organization/40",
                "title": "New organization",
                "text": "You're now member of a new Organization",
                "date": "2023-02-23T16:23:13.122Z",
                "read": True,
            },
            id="with_extra_params_that_will_get_overwritten",
        ),
    ],
)
async def test_create_user_notification(
    logged_user: UserInfoDict,
    notification_redis_client: aioredis.Redis,
    client: TestClient,
    notification_dict: dict[str, Any],
    expected_response: HTTPStatus,
):
    assert client.app
    url = client.app.router["create_user_notification"].url_for()
    assert str(url) == "/v0/me/notifications"
    notification_dict["user_id"] = logged_user["id"]
    resp = await client.post(url.path, json=notification_dict)
    data, error = await assert_status(resp, expected_response)
    assert data is None  # 204...

    if not error:
        user_id = logged_user["id"]
        user_notifications = await _get_user_notifications(
            notification_redis_client, user_id
        )
        assert len(user_notifications) == 1
        # these are always generated and overwritten, even if provided by the user, since
        # we do not want to overwrite existing ones
        assert user_notifications[0].read is False
        assert user_notifications[0].id != notification_dict.get("id", None)
    else:
        assert error is not None


@pytest.mark.parametrize("user_role", [(UserRole.USER)])
@pytest.mark.parametrize(
    "notification_count",
    [
        0,
        MAX_NOTIFICATIONS_FOR_USER_TO_KEEP - 1,
        MAX_NOTIFICATIONS_FOR_USER_TO_KEEP,
        MAX_NOTIFICATIONS_FOR_USER_TO_KEEP + 1,
        MAX_NOTIFICATIONS_FOR_USER_TO_KEEP * 10,
    ],
)
async def test_create_user_notification_capped_list_length(
    logged_user: UserInfoDict,
    notification_redis_client: aioredis.Redis,
    client: TestClient,
    notification_count: int,
):
    assert client.app
    url = client.app.router["create_user_notification"].url_for()
    assert str(url) == "/v0/me/notifications"

    notifications_create_results = await asyncio.gather(
        *(
            client.post(
                url.path,
                json={
                    "user_id": "1",
                    "category": NotificationCategory.NEW_ORGANIZATION,
                    "actionable_path": "organization/40",
                    "title": "New organization",
                    "text": "You're now member of a new Organization",
                    "date": "2023-02-23T16:23:13.122Z",
                },
            )
            for _ in range(notification_count)
        )
    )
    assert (
        all(
            x.status == status.HTTP_204_NO_CONTENT for x in notifications_create_results
        )
        is True
    )

    user_id = logged_user["id"]
    user_notifications = await _get_user_notifications(
        notification_redis_client, user_id
    )
    assert len(user_notifications) <= MAX_NOTIFICATIONS_FOR_USER_TO_KEEP


@pytest.mark.parametrize(
    "user_role,expected_response",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_403_FORBIDDEN),
        (UserRole.USER, status.HTTP_204_NO_CONTENT),
        (UserRole.TESTER, status.HTTP_204_NO_CONTENT),
    ],
)
async def test_update_user_notification(
    logged_user: UserInfoDict,
    notification_redis_client: aioredis.Redis,
    client: TestClient,
    expected_response: HTTPStatus,
):
    async with _create_notifications(
        notification_redis_client, logged_user, 1
    ) as created_notifications:
        assert client.app
        for notification in created_notifications:
            url = client.app.router["mark_notification_as_read"].url_for(
                notification_id=f"{notification.id}"
            )
            assert str(url) == f"/v0/me/notifications/{notification.id}"
            assert notification.read is False

            resp = await client.patch(url.path, json={"read": True})
            await assert_status(resp, expected_response)


@pytest.mark.parametrize("user_role", [UserRole.USER])
@pytest.mark.parametrize(
    "notification_count",
    [1, MAX_NOTIFICATIONS_FOR_USER_TO_SHOW, MAX_NOTIFICATIONS_FOR_USER_TO_SHOW + 1],
)
async def test_update_user_notification_at_correct_index(
    logged_user: UserInfoDict,
    notification_redis_client: aioredis.Redis,
    client: TestClient,
    notification_count: int,
):
    assert client.app
    user_id = logged_user["id"]

    async def _get_stored_notifications() -> list[UserNotification]:
        return [
            UserNotification.parse_raw(x)
            for x in await notification_redis_client.lrange(
                get_notification_key(user_id), 0, -1
            )
        ]

    def _marked_as_read(
        notifications: list[UserNotification],
    ) -> list[UserNotification]:
        results = deepcopy(notifications)
        for notification in results:
            notification.read = True
        return results

    async with _create_notifications(
        notification_redis_client, logged_user, notification_count
    ) as created_notifications:
        notifications_before_update = await _get_stored_notifications()
        for notification in created_notifications:
            url = client.app.router["mark_notification_as_read"].url_for(
                notification_id=f"{notification.id}"
            )
            assert str(url) == f"/v0/me/notifications/{notification.id}"
            assert notification.read is False

            resp = await client.patch(url.path, json={"read": True})
            assert resp.status == status.HTTP_204_NO_CONTENT

        notifications_after_update = await _get_stored_notifications()

        for notification in notifications_before_update:
            assert notification.read is False

        for notification in notifications_after_update:
            assert notification.read is True

        # ensure the notifications were updated at the correct index
        assert (
            _marked_as_read(notifications_before_update) == notifications_after_update
        )


@pytest.mark.parametrize(
    "user_role,expected_response",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_200_OK),
        (UserRole.USER, status.HTTP_200_OK),
        (UserRole.TESTER, status.HTTP_200_OK),
    ],
)
async def test_list_permissions(
    logged_user: UserInfoDict,
    client: TestClient,
    expected_response: HTTPStatus,
):
    assert client.app
    url = client.app.router["list_user_permissions"].url_for()
    assert url.path == "/v0/me/permissions"

    resp = await client.get(url.path)
    data, error = await assert_status(resp, expected_response)
    if data:
        assert not error
        list_of_permissions = parse_obj_as(list[PermissionGet], data)
        assert (
            len(list_of_permissions) == 1
        ), "for now there is only 1 permission, but when we sync frontend/backend permissions there will be more"
        assert list_of_permissions[0].name == "override_services_specifications"
        assert list_of_permissions[0].allowed is False, "defaults should be False!"
    else:
        assert data is None
        assert error is not None


@pytest.mark.parametrize(
    "user_role,expected_response",
    [
        (UserRole.USER, status.HTTP_200_OK),
    ],
)
async def test_list_permissions_with_overriden_extra_properties(
    logged_user: UserInfoDict,
    client: TestClient,
    expected_response: HTTPStatus,
    with_permitted_override_services_specifications: None,
):
    assert client.app
    url = client.app.router["list_user_permissions"].url_for()
    assert url.path == "/v0/me/permissions"

    resp = await client.get(url.path)
    data, error = await assert_status(resp, expected_response)
    assert data
    assert not error
    list_of_permissions = parse_obj_as(list[PermissionGet], data)
    filtered_permissions = list(
        filter(
            lambda x: x.name == "override_services_specifications", list_of_permissions
        )
    )
    assert len(filtered_permissions) == 1
    override_services_specifications = filtered_permissions[0]

    assert override_services_specifications.name == "override_services_specifications"
    assert override_services_specifications.allowed is True


@pytest.fixture
async def with_no_product_name_defined(
    aiopg_engine: aiopg.sa.engine.Engine,
) -> AsyncIterator[None]:
    async with aiopg_engine.acquire() as conn:
        result = await conn.execute(products.select())
        assert result
        list_of_products = await result.fetchall()

        # remove them all
        result = await conn.execute(products.delete())
        assert result

    yield

    # revert changes
    if list_of_products:
        async with aiopg_engine.acquire() as conn:
            await conn.execute(
                products.insert().values(
                    [dict(product.items()) for product in list_of_products]
                )
            )


@pytest.mark.xfail(
    reason="Currently no products blocks access to the entire  web API."
    "pcrespov added this marker and notified sanderegg to review test"
)
@pytest.mark.parametrize(
    "user_role,expected_response",
    [
        (UserRole.USER, status.HTTP_200_OK),
    ],
)
async def test_list_permissions_with_no_group_defined_returns_default_false_for_services_override(
    logged_user: UserInfoDict,
    client: TestClient,
    expected_response: HTTPStatus,
    with_no_product_name_defined: None,
):
    assert client.app
    url = client.app.router["list_user_permissions"].url_for()
    assert url.path == "/v0/me/permissions"

    # NOTE: pcrespov -> sanderegg if no products, this request raises HTTPForbidden 403
    resp = await client.get(url.path)
    data, error = await assert_status(resp, expected_response)
    assert data
    assert not error
    list_of_permissions = parse_obj_as(list[PermissionGet], data)
    filtered_permissions = list(
        filter(
            lambda x: x.name == "override_services_specifications", list_of_permissions
        )
    )
    assert len(filtered_permissions) == 1
    override_services_specifications = filtered_permissions[0]

    assert override_services_specifications.name == "override_services_specifications"
    assert override_services_specifications.allowed is False
