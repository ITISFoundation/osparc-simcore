# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import functools
from http import HTTPStatus
from typing import Any
from unittest.mock import MagicMock, Mock

import pytest
import simcore_service_webserver.login._auth_api
from aiohttp.test_utils import TestClient
from aiopg.sa.connection import SAConnection
from faker import Faker
from models_library.generics import Envelope
from psycopg2 import OperationalError
from pytest_simcore.helpers.rawdata_fakers import DEFAULT_TEST_PASSWORD
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.utils_login import UserInfoDict
from servicelib.aiohttp import status
from servicelib.rest_constants import RESPONSE_MODEL_POLICY
from simcore_postgres_database.models.users import UserRole, UserStatus
from simcore_service_webserver.users._preferences_api import (
    get_frontend_user_preferences_aggregation,
)
from simcore_service_webserver.users.schemas import ProfileGet, ProfileUpdate


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

    url = client.app.router["update_my_profile"].url_for()
    assert url.path == "/v0/me"

    resp = await client.put(url.path, json={"last_name": "Foo"})
    _, error = await assert_status(resp, expected)

    if not error:
        resp = await client.get(f"{url}")
        data, _ = await assert_status(resp, status.HTTP_200_OK)

        # This is a PUT! i.e. full replace of profile variable fields!
        assert data["first_name"] == ProfileUpdate.__fields__["first_name"].default
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


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        *(
            (role, status.HTTP_403_FORBIDDEN)
            for role in UserRole
            if role not in {UserRole.PRODUCT_OWNER, UserRole.ANONYMOUS}
        ),
        (UserRole.PRODUCT_OWNER, status.HTTP_200_OK),
    ],
)
async def test_users_api_only_accessed_by_po(
    client: TestClient,
    logged_user: UserInfoDict,
    expected: HTTPStatus,
):
    assert client.app

    url = client.app.router["search_users"].url_for()
    assert url.path == "/v0/users:search"

    resp = await client.get(url.path, params={"email": "do-not-exists@foo.com"})
    await assert_status(resp, expected)


@pytest.mark.acceptance_test(
    "pre-registration in https://github.com/ITISFoundation/osparc-simcore/issues/5138"
)
@pytest.mark.parametrize(
    "user_role",
    [
        UserRole.PRODUCT_OWNER,
    ],
)
async def test_search_and_pre_registration(
    client: TestClient, logged_user: UserInfoDict, faker: Faker
):
    assert client.app

    # ONLY in `users` and NOT `users_pre_registration_details`

    resp = await client.get("/v0/users:search", params={"email": logged_user["email"]})
    assert resp.status == status.HTTP_200_OK

    found, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(found) == 1
    assert found[0] == {
        "firstName": logged_user.get("first_name"),
        "lastName": logged_user.get("last_name"),
        "email": logged_user["email"],
        "companyName": None,
        "phone": logged_user.get("phone"),
        "address": None,
        "city": None,
        "state": None,
        "postalCode": None,
        "country": None,
        "registered": True,
        "status": "ACTIVE",
    }

    # NOT in `users` and ONLY `users_pre_registration_details`

    # create pre-registration
    requester_info = {
        "firstName": faker.first_name(),
        "lastName": faker.last_name(),
        "email": faker.email(),
        "companyName": faker.company(),
        "phone": faker.phone_number(),
        # billing info
        "address": faker.address().replace("\n", ", "),
        "city": faker.city(),
        "state": faker.state(),
        "postalCode": faker.postcode(),
        "country": faker.country(),
    }

    resp = await client.post("/v0/users:pre-register", json=requester_info)
    assert resp.status == status.HTTP_200_OK

    resp = await client.get(
        "/v0/users:search", params={"email": requester_info["email"]}
    )
    found, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(found) == 1

    assert found[0] == {
        **requester_info,
        "registered": False,
        "status": None,
    }

    # Emulating registration of pre-register user
    new_user = (
        await simcore_service_webserver.login._auth_api.create_user(  # noqa: SLF001
            client.app,
            email=requester_info["email"],
            password=DEFAULT_TEST_PASSWORD,
            status_upon_creation=UserStatus.ACTIVE,
            expires_at=None,
        )
    )

    resp = await client.get(
        "/v0/users:search", params={"email": requester_info["email"]}
    )
    found, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(found) == 1

    assert found[0] == {
        **requester_info,
        "registered": True,
        "status": new_user["status"].name,
    }
