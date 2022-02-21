# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import LoggedUser, NewUser, parse_link
from simcore_service_webserver._constants import INDEX_RESOURCE_NAME
from simcore_service_webserver.login.settings import LoginOptions, get_plugin_options
from yarl import URL

NEW_EMAIL = "new@mail.com"


@pytest.fixture
def cfg(client: TestClient) -> LoginOptions:
    cfg = get_plugin_options(client.app)
    assert cfg
    return cfg


async def test_unauthorized_to_change_email(client: TestClient):
    url = client.app.router["auth_change_email"].url_for()
    rsp = await client.post(
        url,
        json={
            "email": NEW_EMAIL,
        },
    )
    assert rsp.status == 401
    await assert_status(rsp, web.HTTPUnauthorized)


async def test_change_to_existing_email(client: TestClient):
    url = client.app.router["auth_change_email"].url_for()

    async with LoggedUser(client) as user:
        async with NewUser(app=client.app) as other:
            rsp = await client.post(
                url,
                json={
                    "email": other["email"],
                },
            )
            await assert_status(
                rsp, web.HTTPUnprocessableEntity, "This email cannot be used"
            )


async def test_change_and_confirm(client: TestClient, cfg: LoginOptions, capsys):

    url = client.app.router["auth_change_email"].url_for()
    index_url = client.app.router[INDEX_RESOURCE_NAME].url_for()
    login_url = client.app.router["auth_login"].url_for()
    logout_url = client.app.router["auth_logout"].url_for()

    assert index_url.path == URL(cfg.LOGIN_REDIRECT).path

    async with LoggedUser(client) as user:
        # request change email
        rsp = await client.post(
            url,
            json={
                "email": NEW_EMAIL,
            },
        )
        assert rsp.url_obj.path == url.path
        await assert_status(rsp, web.HTTPOk, cfg.MSG_CHANGE_EMAIL_REQUESTED)

        # email sent
        out, err = capsys.readouterr()
        link = parse_link(out)

        # try new email but logout first
        rsp = await client.post(logout_url)
        assert rsp.url_obj.path == logout_url.path
        await assert_status(rsp, web.HTTPOk, cfg.MSG_LOGGED_OUT)

        # click email's link
        rsp = await client.get(link)
        txt = await rsp.text()

        assert rsp.url_obj.path == index_url.path
        assert (
            "This is a result of disable_static_webserver fixture for product OSPARC"
            in txt
        )

        rsp = await client.post(
            login_url,
            json={
                "email": NEW_EMAIL,
                "password": user["raw_password"],
            },
        )
        payload = await rsp.json()
        assert rsp.url_obj.path == login_url.path
        await assert_status(rsp, web.HTTPOk, cfg.MSG_LOGGED_IN)
