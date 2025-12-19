# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import AsyncIterable

import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole
from models_library.api_schemas_webserver.groups import GroupUserGet
from models_library.api_schemas_webserver.users import (
    UserGet,
)
from pydantic import TypeAdapter
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.webserver_login import (
    switch_client_session_to,
)
from pytest_simcore.helpers.webserver_users import NewUser, UserInfoDict
from servicelib.aiohttp import status


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
            # Maximum privacy
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
            # Medium privacy
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
            # Fully public
            "privacy_hide_username": False,
            "privacy_hide_email": False,
            "privacy_hide_fullname": False,
        },
    ) as usr:
        yield usr


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
        .with_query(email=partial_email.upper())  # NOTE: case insensitive!
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
