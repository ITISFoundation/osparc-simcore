# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from aiohttp import web
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import LoggedUser, NewUser, parse_link
from simcore_service_webserver.constants import INDEX_RESOURCE_NAME
from simcore_service_webserver.login.cfg import APP_LOGIN_CONFIG
from yarl import URL

NEW_EMAIL = "new@mail.com"


async def test_unauthorized_to_change_email(client):
    url = client.app.router["auth_change_email"].url_for()
    rsp = await client.post(
        url,
        json={
            "email": NEW_EMAIL,
        },
    )
    assert rsp.status == 401
    await assert_status(rsp, web.HTTPUnauthorized)


async def test_change_to_existing_email(client):
    url = client.app.router["auth_change_email"].url_for()

    async with LoggedUser(client) as user:
        async with NewUser() as other:
            rsp = await client.post(
                url,
                json={
                    "email": other["email"],
                },
            )
            await assert_status(
                rsp, web.HTTPUnprocessableEntity, "This email cannot be used"
            )


async def test_change_and_confirm(client, capsys):
    cfg = client.app[APP_LOGIN_CONFIG]

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


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "--maxfail=1"])
