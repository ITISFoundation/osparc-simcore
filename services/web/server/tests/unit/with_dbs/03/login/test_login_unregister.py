# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.login._constants import MSG_USER_DELETED


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_mark_account_for_deletion(
    client: TestClient, logged_user: UserInfoDict, mocker: MockerFixture
):
    mock = mocker.patch(
        "simcore_service_webserver.email._core._do_send_mail",
        spec=True,
    )

    # is logged in
    response = await client.get("/v0/me")
    await assert_status(response, web.HTTPOk)

    # failed check to delete account
    response = await client.post(
        "/v0/me:mark-deleted",
        json={
            "email": "WrongEmail@email.com",
            "password": "foo",
        },
    )
    await assert_status(response, web.HTTPConflict)

    # success to request deletion of account
    response = await client.post(
        "/v0/me:mark-deleted",
        json={
            "email": logged_user["email"],
            "password": logged_user["raw_password"],
        },
    )
    await assert_status(response, web.HTTPOk)

    # sent email?
    mimetext = mock.call_args[1]["message"]
    assert mimetext["Subject"]
    assert mimetext["To"] == logged_user["email"]

    # should be logged-out
    response = await client.get("/v0/me")
    await assert_status(response, web.HTTPUnauthorized)

    # try to login again and get rejected
    response = await client.post(
        "/v0/auth/login",
        json={"email": logged_user["email"], "password": logged_user["raw_password"]},
    )
    _, error = await assert_status(response, web.HTTPUnauthorized)

    prefix_msg = MSG_USER_DELETED.format(support_email="").strip()
    assert prefix_msg in error["errors"][0]["message"]
