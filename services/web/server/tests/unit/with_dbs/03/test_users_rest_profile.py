# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import functools
from collections.abc import AsyncIterator
from copy import deepcopy
from http import HTTPStatus
from typing import Any
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from aiopg.sa.connection import SAConnection
from common_library.users_enums import UserRole
from models_library.api_schemas_webserver.users import (
    MyProfileRestGet,
)
from models_library.groups import AccessRightsDict
from psycopg2 import OperationalError
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.aiohttp import status
from servicelib.rest_constants import RESPONSE_MODEL_POLICY
from simcore_service_webserver.products._models import Product
from simcore_service_webserver.user_preferences._service import (
    get_frontend_user_preferences_aggregation,
)
from sqlalchemy.exc import OperationalError as SQLAlchemyOperationalError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


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
            "WEBSERVER_DEV_FEATURES_ENABLED": "1",  # NOTE: still under development
        },
    )


@pytest.fixture
async def support_group_before_app_starts(
    asyncpg_engine: AsyncEngine,
    product_name: str,
) -> AsyncIterator[dict[str, Any]]:
    """Creates a standard support group and assigns it to the current product"""
    from pytest_simcore.helpers.postgres_tools import insert_and_get_row_lifespan
    from simcore_postgres_database.models.groups import groups
    from simcore_postgres_database.models.products import products

    # Create support group using direct database insertion
    group_values = {
        "name": "Support Group",
        "description": "Support group for product",
        "type": "STANDARD",
    }

    # pylint: disable=contextmanager-generator-missing-cleanup
    async with insert_and_get_row_lifespan(
        asyncpg_engine,
        table=groups,
        values=group_values,
        pk_col=groups.c.gid,
    ) as group_row:
        group_id = group_row["gid"]

        # Update product to set support_standard_group_id
        async with asyncpg_engine.begin() as conn:
            await conn.execute(
                sa.update(products)
                .where(products.c.name == product_name)
                .values(support_standard_group_id=group_id)
            )

        yield group_row
        # group will be deleted after test


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        *((r, status.HTTP_200_OK) for r in UserRole if r >= UserRole.GUEST),
    ],
)
async def test_access_rights_on_get_profile(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    expected: HTTPStatus,
):
    assert client.app

    url = client.app.router["get_my_profile"].url_for()
    assert url.path == "/v0/me"

    resp = await client.get(f"{url}")
    await assert_status(resp, expected)


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_403_FORBIDDEN),
        *((r, status.HTTP_204_NO_CONTENT) for r in UserRole if r >= UserRole.USER),
    ],
)
async def test_access_update_profile(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    expected: HTTPStatus,
):
    assert client.app

    url = client.app.router["update_my_profile"].url_for()
    assert url.path == "/v0/me"

    resp = await client.patch(f"{url}", json={"last_name": "Foo"})
    await assert_status(resp, expected)


@pytest.fixture
def product(client: TestClient, osparc_product_name: str) -> Product:
    assert client.app
    from simcore_service_webserver.products import products_service

    return products_service.get_product(client.app, osparc_product_name)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_get_profile_user_not_in_support_group(
    support_group_before_app_starts: dict[str, Any],
    # after app starts because it modifies the product
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    primary_group: dict[str, Any],
    standard_groups: list[dict[str, Any]],
    all_group: dict[str, str],
    product: Product,
):
    assert client.app

    url = client.app.router["get_my_profile"].url_for()
    assert url.path == "/v0/me"

    resp = await client.get(f"{url}")
    data, error = await assert_status(resp, status.HTTP_200_OK)

    assert not error
    profile = MyProfileRestGet.model_validate(data)

    assert profile.login == logged_user["email"]
    assert profile.first_name == logged_user.get("first_name", None)
    assert profile.last_name == logged_user.get("last_name", None)
    assert profile.role == user_role.name
    assert profile.groups
    assert profile.expiration_date is None

    got_profile_groups = profile.groups.model_dump(**RESPONSE_MODEL_POLICY, mode="json")
    assert got_profile_groups["me"] == primary_group
    assert got_profile_groups["all"] == all_group
    assert got_profile_groups["product"] == {
        "accessRights": {"delete": False, "read": False, "write": False},
        "description": "osparc product group",
        "gid": product.group_id,
        "label": "osparc",
        "thumbnail": None,
    }

    # support group exists
    assert got_profile_groups["support"]
    support_group_id = got_profile_groups["support"]["gid"]

    assert support_group_id == support_group_before_app_starts["gid"]
    assert (
        got_profile_groups["support"]["description"]
        == support_group_before_app_starts["description"]
    )
    assert "accessRights" not in got_profile_groups["support"]

    # standard groups with at least read access
    sorted_by_group_id = functools.partial(sorted, key=lambda d: d["gid"])
    assert sorted_by_group_id(
        got_profile_groups["organizations"]
    ) == sorted_by_group_id(standard_groups)

    # user is NOT part of the support group
    all_standard_groups_ids = {g["gid"] for g in standard_groups}
    assert support_group_id not in all_standard_groups_ids

    # preferences
    assert profile.preferences == await get_frontend_user_preferences_aggregation(
        client.app, user_id=logged_user["id"], product_name="osparc"
    )


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_get_profile_user_in_support_group(
    support_group_before_app_starts: dict[str, Any],
    # after app starts because it modifies the product
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    primary_group: dict[str, Any],
    standard_groups: list[dict[str, Any]],
    all_group: dict[str, str],
    product: Product,
):
    assert client.app
    from simcore_service_webserver.groups import _groups_repository

    # Now add user to support group with read-only access
    await _groups_repository.add_new_user_in_group(
        client.app,
        group_id=support_group_before_app_starts["gid"],
        new_user_id=logged_user["id"],
        access_rights=AccessRightsDict(read=True, write=False, delete=False),
    )

    url = client.app.router["get_my_profile"].url_for()
    assert url.path == "/v0/me"

    resp = await client.get(f"{url}")
    data, error = await assert_status(resp, status.HTTP_200_OK)

    assert not error
    profile = MyProfileRestGet.model_validate(data)

    assert profile.login == logged_user["email"]
    assert profile.first_name == logged_user.get("first_name", None)
    assert profile.last_name == logged_user.get("last_name", None)
    assert profile.role == user_role.name
    assert profile.groups
    assert profile.expiration_date is None

    got_profile_groups = profile.groups.model_dump(**RESPONSE_MODEL_POLICY, mode="json")
    assert got_profile_groups["me"] == primary_group
    assert got_profile_groups["all"] == all_group
    assert got_profile_groups["product"] == {
        "accessRights": {"delete": False, "read": False, "write": False},
        "description": "osparc product group",
        "gid": product.group_id,
        "label": "osparc",
        "thumbnail": None,
    }

    # support group exists
    assert got_profile_groups["support"]
    support_group_id = got_profile_groups["support"]["gid"]

    assert support_group_id == support_group_before_app_starts["gid"]
    assert (
        got_profile_groups["support"]["description"]
        == support_group_before_app_starts["description"]
    )
    assert "accessRights" not in got_profile_groups["support"]

    # When user is part of support group, it should appear in standard groups
    sorted_by_group_id = functools.partial(sorted, key=lambda d: d["gid"])
    expected_standard_groups = [
        *standard_groups,
        {
            "gid": support_group_id,
            "label": support_group_before_app_starts["name"],
            "description": support_group_before_app_starts["description"],
            "thumbnail": None,
            "accessRights": {"read": True, "write": False, "delete": False},
        },
    ]
    assert sorted_by_group_id(
        got_profile_groups["organizations"]
    ) == sorted_by_group_id(expected_standard_groups)
    assert support_group_id in {g["gid"] for g in got_profile_groups["organizations"]}


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_update_profile(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
):
    assert client.app

    # GET
    url = client.app.router["get_my_profile"].url_for()
    resp = await client.get(f"{url}")

    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data["role"] == user_role.name
    before = deepcopy(data)

    # UPDATE
    url = client.app.router["update_my_profile"].url_for()
    resp = await client.patch(
        f"{url}",
        json={
            "last_name": "Foo",
        },
    )
    _, error = await assert_status(resp, status.HTTP_204_NO_CONTENT)
    assert not error

    # GET
    url = client.app.router["get_my_profile"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    assert data["last_name"] == "Foo"

    def _copy(data: dict, exclude: set) -> dict:
        return {k: v for k, v in data.items() if k not in exclude}

    exclude = {"last_name"}
    assert _copy(data, exclude) == _copy(before, exclude)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_profile_workflow(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
):
    assert client.app

    url = client.app.router["get_my_profile"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    my_profile = MyProfileRestGet.model_validate(data)

    url = client.app.router["update_my_profile"].url_for()
    resp = await client.patch(
        f"{url}",
        json={
            "first_name": "Odei",  # NOTE: still not camecase!
            "userName": "odei123",
            "privacy": {"hideFullname": False},
        },
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    url = client.app.router["get_my_profile"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    updated_profile = MyProfileRestGet.model_validate(data)

    assert updated_profile.first_name != my_profile.first_name
    assert updated_profile.last_name == my_profile.last_name
    assert updated_profile.login == my_profile.login

    assert updated_profile.user_name != my_profile.user_name
    assert updated_profile.user_name == "odei123"

    assert updated_profile.privacy != my_profile.privacy
    assert updated_profile.privacy.hide_username == my_profile.privacy.hide_username
    assert updated_profile.privacy.hide_email == my_profile.privacy.hide_email
    assert updated_profile.privacy.hide_fullname != my_profile.privacy.hide_fullname


@pytest.mark.parametrize("user_role", [UserRole.USER])
@pytest.mark.parametrize("invalid_username", ["", "_foo", "superadmin", "foo..-123"])
async def test_update_wrong_user_name(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    invalid_username: str,
):
    assert client.app

    url = client.app.router["update_my_profile"].url_for()
    resp = await client.patch(
        f"{url}",
        json={
            "userName": invalid_username,
        },
    )
    await assert_status(resp, status.HTTP_422_UNPROCESSABLE_ENTITY)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_update_existing_user_name(
    user_role: UserRole,
    user: UserInfoDict,
    logged_user: UserInfoDict,
    client: TestClient,
):
    assert client.app

    other_username = user["name"]
    assert other_username != logged_user["name"]

    #  update with SAME username (i.e. existing)
    url = client.app.router["get_my_profile"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    assert data["userName"] == logged_user["name"]

    url = client.app.router["update_my_profile"].url_for()
    resp = await client.patch(
        f"{url}",
        json={
            "userName": other_username,
        },
    )
    await assert_status(resp, status.HTTP_409_CONFLICT)


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.USER, status.HTTP_503_SERVICE_UNAVAILABLE),
    ],
)
async def test_get_profile_with_failing_db_connection(
    logged_user: UserInfoDict,
    client: TestClient,
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

    with patch.object(SAConnection, "execute") as mock_sa_execute, patch.object(
        AsyncConnection, "execute"
    ) as mock_async_execute:

        # Emulates a database connection failure
        mock_sa_execute.side_effect = OperationalError(
            "MOCK: server closed the connection unexpectedly"
        )
        mock_async_execute.side_effect = SQLAlchemyOperationalError(
            statement="MOCK statement",
            params=(),
            orig=OperationalError("MOCK: server closed the connection unexpectedly"),
        )

        resp = await client.get(url.path)

        data, error = await assert_status(resp, expected)
        assert not data
        assert error["message"] == "Authentication service is temporary unavailable"
