# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import functools
from collections.abc import AsyncIterable
from copy import deepcopy
from http import HTTPStatus
from typing import Any
from unittest.mock import patch

import pytest
from aiohttp.test_utils import TestClient
from aiopg.sa.connection import SAConnection
from common_library.users_enums import UserRole
from models_library.api_schemas_webserver.groups import GroupUserGet
from models_library.api_schemas_webserver.users import (
    MyProfileGet,
    UserGet,
)
from psycopg2 import OperationalError
from pydantic import TypeAdapter
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.webserver_login import (
    switch_client_session_to,
)
from pytest_simcore.helpers.webserver_users import NewUser, UserInfoDict
from servicelib.aiohttp import status
from servicelib.rest_constants import RESPONSE_MODEL_POLICY
from simcore_service_webserver.user_preferences._service import (
    get_frontend_user_preferences_aggregation,
)
from sqlalchemy.exc import OperationalError as SQLAlchemyOperationalError
from sqlalchemy.ext.asyncio import AsyncConnection


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


@pytest.fixture
def partial_first_name() -> str:
    return "Jaimito"


@pytest.fixture
def partial_username() -> str:
    return "COMMON_USERNAME"


@pytest.fixture
def partial_email() -> str:
    return "@acme.com"


@pytest.fixture
async def private_user(
    client: TestClient,
    partial_username: str,
    partial_email: str,
    partial_first_name: str,
) -> AsyncIterable[UserInfoDict]:
    assert client.app
    async with NewUser(
        app=client.app,
        user_data={
            "name": f"james{partial_username}",
            "first_name": partial_first_name,
            "last_name": "Bond",
            "email": f"james{partial_email}",
            "privacy_hide_username": True,
            "privacy_hide_email": True,
            "privacy_hide_fullname": True,
        },
    ) as usr:
        yield usr


@pytest.fixture
async def semi_private_user(
    client: TestClient, partial_username: str, partial_first_name: str
) -> AsyncIterable[UserInfoDict]:
    assert client.app
    async with NewUser(
        app=client.app,
        user_data={
            "name": f"maxwell{partial_username}",
            "first_name": partial_first_name,
            "last_name": "Maxwell",
            "email": "j@maxwell.me",
            "privacy_hide_username": False,
            "privacy_hide_email": True,
            "privacy_hide_fullname": False,  # <--
        },
    ) as usr:
        yield usr


@pytest.fixture
async def public_user(
    client: TestClient, partial_username: str, partial_email: str
) -> AsyncIterable[UserInfoDict]:
    assert client.app
    async with NewUser(
        app=client.app,
        user_data={
            "name": f"taylor{partial_username}",
            "first_name": "Taylor",
            "last_name": "Swift",
            "email": f"taylor{partial_email}",
            "privacy_hide_username": False,
            "privacy_hide_email": False,
            "privacy_hide_fullname": False,
        },
    ) as usr:
        yield usr


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_search_users_by_partial_fullname(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    partial_first_name: str,
    private_user: UserInfoDict,
    semi_private_user: UserInfoDict,
    public_user: UserInfoDict,
):
    assert client.app
    assert user_role == logged_user["role"]

    # logged_user has default settings
    assert private_user["id"] != logged_user["id"]
    assert public_user["id"] != logged_user["id"]

    # SEARCH by partial first_name
    assert partial_first_name in private_user.get("first_name", "")
    assert partial_first_name in semi_private_user.get("first_name", "")
    assert partial_first_name not in public_user.get("first_name", "")

    url = client.app.router["search_users"].url_for()
    resp = await client.post(f"{url}", json={"match": partial_first_name})
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    # expected `semi_private_user` found
    found = TypeAdapter(list[UserGet]).validate_python(data)
    assert found
    assert len(found) == 1
    assert found[0].user_name == semi_private_user["name"]
    assert found[0].first_name == semi_private_user.get("first_name")
    assert found[0].last_name == semi_private_user.get("last_name")
    assert found[0].email is None


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_search_users_by_partial_email(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    partial_email: str,
    public_user: UserInfoDict,
    semi_private_user: UserInfoDict,
    private_user: UserInfoDict,
):

    # SEARCH by partial email
    assert partial_email in private_user["email"]
    assert partial_email not in semi_private_user["email"]
    assert partial_email in public_user["email"]

    url = client.app.router["search_users"].url_for()
    resp = await client.post(f"{url}", json={"match": partial_email})
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    found = TypeAdapter(list[UserGet]).validate_python(data)
    assert found
    assert len(found) == 1

    # expected `public_user` found
    assert found[0].user_id == public_user["id"]
    assert found[0].user_name == public_user["name"]
    assert found[0].email == public_user["email"]
    assert found[0].first_name == public_user.get("first_name")
    assert found[0].last_name == public_user.get("last_name")

    # SEARCH user for admin (from a USER)
    url = (
        client.app.router["search_user_accounts"]
        .url_for()
        .with_query(email=partial_email)
    )
    resp = await client.get(f"{url}")
    await assert_status(resp, status.HTTP_403_FORBIDDEN)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_search_users_by_partial_username(
    logged_user: UserInfoDict,
    client: TestClient,
    partial_username: str,
    public_user: UserInfoDict,
    semi_private_user: UserInfoDict,
    private_user: UserInfoDict,
):
    assert client.app

    # SEARCH by partial username
    assert partial_username in private_user["name"]
    assert partial_username in semi_private_user["name"]
    assert partial_username in public_user["name"]

    url = client.app.router["search_users"].url_for()
    resp = await client.post(f"{url}", json={"match": partial_username})
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    found = TypeAdapter(list[UserGet]).validate_python(data)
    assert found
    assert len(found) == 2

    # expected `public_user` found
    index = [u.user_id for u in found].index(public_user["id"])
    assert found[index].user_name == public_user["name"]
    assert found[index].email == public_user["email"]
    assert found[index].first_name == public_user.get("first_name")
    assert found[index].last_name == public_user.get("last_name")

    # expected `semi_private_user` found
    index = (index + 1) % 2
    assert found[index].user_name == semi_private_user["name"]
    assert found[index].email is None
    assert found[index].first_name == semi_private_user.get("first_name")
    assert found[index].last_name == semi_private_user.get("last_name")


async def test_search_myself(
    client: TestClient,
    public_user: UserInfoDict,
    semi_private_user: UserInfoDict,
    private_user: UserInfoDict,
):
    assert client.app
    for user in [public_user, semi_private_user, private_user]:
        async with switch_client_session_to(client, user):

            # search me
            url = client.app.router["search_users"].url_for()
            resp = await client.post(f"{url}", json={"match": user["name"]})
            data, _ = await assert_status(resp, status.HTTP_200_OK)

            found = TypeAdapter(list[UserGet]).validate_python(data)
            assert found
            assert len(found) == 1

            # I can see my own data
            assert found[0].user_name == user["name"]
            assert found[0].email == user["email"]
            assert found[0].first_name == user.get("first_name")
            assert found[0].last_name == user.get("last_name")


@pytest.mark.acceptance_test(
    "https://github.com/ITISFoundation/osparc-issues/issues/1779"
)
@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_get_user_by_group_id(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    public_user: UserInfoDict,
    private_user: UserInfoDict,
):
    assert client.app
    assert user_role == logged_user["role"]

    assert private_user["id"] != logged_user["id"]
    assert public_user["id"] != logged_user["id"]

    # GET public_user by its primary gid
    url = client.app.router["get_all_group_users"].url_for(
        gid=f"{public_user['primary_gid']}"
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    users = TypeAdapter(list[GroupUserGet]).validate_python(data)
    assert len(users) == 1
    assert users[0].id == public_user["id"]
    assert users[0].user_name == public_user["name"]
    assert users[0].first_name == public_user.get("first_name")
    assert users[0].last_name == public_user.get("last_name")

    # GET private_user by its primary gid
    url = client.app.router["get_all_group_users"].url_for(
        gid=f"{private_user['primary_gid']}"
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    users = TypeAdapter(list[GroupUserGet]).validate_python(data)
    assert len(users) == 1
    assert users[0].id == private_user["id"]
    assert users[0].user_name is None, "It's private"
    assert users[0].first_name is None, "It's private"
    assert users[0].last_name is None, "It's private"


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


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_get_profile(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    primary_group: dict[str, Any],
    standard_groups: list[dict[str, Any]],
    all_group: dict[str, str],
):
    assert client.app

    url = client.app.router["get_my_profile"].url_for()
    assert url.path == "/v0/me"

    resp = await client.get(f"{url}")
    data, error = await assert_status(resp, status.HTTP_200_OK)

    assert not error
    profile = MyProfileGet.model_validate(data)

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
        "gid": 2,
        "label": "osparc",
        "thumbnail": None,
    }

    sorted_by_group_id = functools.partial(sorted, key=lambda d: d["gid"])
    assert sorted_by_group_id(
        got_profile_groups["organizations"]
    ) == sorted_by_group_id(standard_groups)

    assert profile.preferences == await get_frontend_user_preferences_aggregation(
        client.app, user_id=logged_user["id"], product_name="osparc"
    )


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
    my_profile = MyProfileGet.model_validate(data)

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
    updated_profile = MyProfileGet.model_validate(data)

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


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_get_and_update_phone_in_profile(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
):
    assert client.app

    # GET initial profile
    url = client.app.router["get_my_profile"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    initial_profile = MyProfileGet.model_validate(data)
    initial_phone = initial_profile.phone

    # UPDATE phone number
    new_phone = "+34 123 456 789"
    url = client.app.router["update_my_profile"].url_for()
    resp = await client.patch(
        f"{url}",
        json={
            "phone": new_phone,
        },
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # GET updated profile
    url = client.app.router["get_my_profile"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    updated_profile = MyProfileGet.model_validate(data)

    # Verify phone was updated
    assert updated_profile.phone == new_phone
    assert updated_profile.phone != initial_phone

    # Verify other fields remained unchanged
    assert updated_profile.first_name == initial_profile.first_name
    assert updated_profile.last_name == initial_profile.last_name
    assert updated_profile.login == initial_profile.login
    assert updated_profile.user_name == initial_profile.user_name

    # UPDATE phone to None (clear it)
    url = client.app.router["update_my_profile"].url_for()
    resp = await client.patch(
        f"{url}",
        json={
            "phone": None,
        },
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # GET profile after clearing phone
    url = client.app.router["get_my_profile"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    cleared_profile = MyProfileGet.model_validate(data)
    assert cleared_profile.phone is None
