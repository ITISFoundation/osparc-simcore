# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import attr
import pytest
from aiohttp import web

from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import LoggedUser
from simcore_service_webserver.db_models import UserRole
from simcore_service_webserver.login.api_keys_handlers import CRUD as ApiKeysCRUD


@pytest.fixture()
async def logged_user(client, user_role: UserRole):
    """ adds a user in db and logs in with client

    NOTE: `user_role` fixture is defined as a parametrization below!!!
    """
    async with LoggedUser(
        client,
        {"role": user_role.name},
        check_if_succeeds=user_role != UserRole.ANONYMOUS,
    ) as user:
        print("-----> logged in user as", user_role)
        yield user
        print("<----- logged out user as", user_role)


@pytest.fixture()
async def fake_user_api_keys(client, logged_user):
    names = ["foo", "bar", "beta", "alpha"]

    @attr.s(auto_attribs=True)
    class Adapter:
        app: web.Application
        userid: int

        def get(self, *_args):
            return self.userid

    crud = ApiKeysCRUD(Adapter(client.app, logged_user['id']))

    for name in names:
        await crud.create(name, api_key=f"{name}-key", api_secret=f"{name}-secret")

    yield names

    for name in names:
        await crud.delete_api_key(name)


# TESTS ---------

USER_ACCESS_PARAMETERS = [
    (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPUnauthorized),
    (UserRole.USER, web.HTTPOk),
    (UserRole.TESTER, web.HTTPOk),
]


@pytest.mark.parametrize(
    "user_role,expected", USER_ACCESS_PARAMETERS,
)
async def test_list_api_keys(client, logged_user, user_role, expected):
    resp = await client.get("/v0/auth/api-keys")
    data, errors = await assert_status(resp, expected)

    if not errors:
        assert not data


@pytest.mark.parametrize("user_role,expected", USER_ACCESS_PARAMETERS)
async def test_create_api_keys(client, logged_user, user_role, expected):
    resp = await client.post("/v0/auth/api-keys", json={"display_name": "foo"})

    data, errors = await assert_status(resp, expected)

    if not errors:
        assert data["display_name"] == "foo"
        assert "api_key" in data
        assert "api_secret" in data

        resp = await client.get("/v0/auth/api-keys")
        data, _ = await assert_status(resp, expected)
        assert sorted(data) == [
            "foo",
        ]


@pytest.mark.parametrize("user_role,expected", [
    (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPUnauthorized),
    (UserRole.USER, web.HTTPNoContent),
    (UserRole.TESTER, web.HTTPNoContent),
])
async def test_delete_api_keys(
    client, fake_user_api_keys, logged_user, user_role, expected
):
    resp = await client.delete("/v0/auth/api-keys", json={"display_name": "foo"})
    await assert_status(resp, expected)

    for name in fake_user_api_keys:
        resp = await client.delete("/v0/auth/api-keys", json={"display_name": name})
        await assert_status(resp, expected)
