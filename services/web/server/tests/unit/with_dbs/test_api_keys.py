# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
from aiohttp import web
import pytest

from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import LoggedUser
from simcore_service_webserver.db_models import UserRole


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
        print("-----> logged in user", user_role)
        yield user
        print("<----- logged out user", user_role)


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPOk),
        (UserRole.USER, web.HTTPOk),
        (UserRole.TESTER, web.HTTPOk),
    ],
)
async def test_create_api_keys(client, logged_user, user_role, expected):
    resp = await client.post("/v0/auth/api-keys", json={"display_name": "foo"})

    data, errors = await assert_status(resp, expected)

    if not errors:
        client.app


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPOk),
        (UserRole.USER, web.HTTPOk),
        (UserRole.TESTER, web.HTTPOk),
    ],
)
async def test_list_api_keys(client, logged_user, user_role, expected):
    resp = await client.get("/v0/auth/api-keys")
    data, errors = await assert_status(resp, expected)

    if not errors:
        assert not data

        with UserApiKeys(client.app, logged_user.user.user_id, ['foo', 'bar', 'beta']):
            resp = await client.get("/v0/auth/api-keys")
            data, _ = await assert_status(resp, expected)
            assert data == ['foo', 'bar', 'beta']

@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPNoContent),
        (UserRole.USER, web.HTTPNoContent),
        (UserRole.TESTER, web.HTTPNoContent),
    ],
)
async def test_delete_api_keys(client, logged_user, user_role, expected):
    resp = await client.delete("/v0/auth/api-keys", json={"display_name": "foo"})
    data, errors = await assert_status(resp, expected)
