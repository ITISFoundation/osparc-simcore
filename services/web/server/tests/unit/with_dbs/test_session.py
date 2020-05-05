# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import pytest
from aiohttp import web
from aiohttp_session import get_session as get_aiohttp_session

from pytest_simcore.helpers.utils_login import LoggedUser, NewUser
from simcore_service_webserver.application import create_application
from simcore_service_webserver.login.cfg import get_storage


@pytest.fixture
def client(loop, aiohttp_client, app_cfg, monkeypatch, postgres_db):

    extra_test_routes = web.RouteTableDef()

    @extra_test_routes.get("/session")
    async def return_session(request: web.Request):
        session = await get_aiohttp_session(request)
        return web.json_response(dict(session))

    @extra_test_routes.get("/delete_user_email")
    async def delete_user_email(request: web.Request):
        session = await get_aiohttp_session(request)
        del session["user_email"]
        return web.HTTPOk()

    app = create_application(app_cfg)
    app.add_routes(extra_test_routes)

    return loop.run_until_complete(
        aiohttp_client(
            app,
            server_kwargs={
                "port": app_cfg["main"]["port"],
                "host": app_cfg["main"]["host"],
            },
        )
    )


async def test_login_logout(client):
    # Tests that login sets the user_email and logout removes it
    login_url = client.app.router["auth_login"].url_for()
    logout_url = client.app.router["auth_logout"].url_for()
    session_url = "/session"
    async with NewUser() as user:
        resp = await client.get(session_url)
        session = await resp.json()
        assert session.get("user_email") == None

        # login
        await client.post(
            login_url, json={"email": user["email"], "password": user["raw_password"]}
        )
        resp = await client.get(session_url)
        session = await resp.json()
        assert session.get("user_email") == user["email"]

        # logout
        await client.post(logout_url)
        resp = await client.get(session_url)
        session = await resp.json()
        assert session.get("user_email") == None


async def test_me(client):
    # NOTE: /me enforces session creation for the following edge case:
    #
    # Q: Why do you need to set this value in two handlers (user_handers and login handler)?? Shoudn't be enough only upon login?
    # A: This is because once it deploys, the users already logged in, that don't have to go through the login endpoint, won't get this inside
    #    their sessions unless they logout and login again
    #

    # Tests that /me sets de user_email
    db = get_storage(client.app)
    session_url = "/session"
    delete_user_email_url = "/delete_user_email"
    me_url = client.app.router["get_my_profile"].url_for()
    async with LoggedUser(client) as user:
        # Forces deletion of session['user_email']
        await client.get(delete_user_email_url)
        resp = await client.get(session_url)
        session = await resp.json()
        assert session.get("user_email") == None

        # recovers session['user_email'] when /me is called
        await client.get(me_url)
        resp = await client.get(session_url)
        session = await resp.json()
        assert session.get("user_email") == user["email"]
    await db.delete_user(user)
