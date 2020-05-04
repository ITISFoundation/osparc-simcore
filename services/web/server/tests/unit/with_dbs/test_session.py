from pytest_simcore.helpers.utils_login import LoggedUser, NewUser
from simcore_service_webserver.login.cfg import get_storage


async def test_login_logout(client):
    # Tests that login sets the user_email and logout removes it
    login_url = client.app.router["auth_login"].url_for()
    logout_url = client.app.router["auth_logout"].url_for()
    session_url = "/session"
    async with NewUser() as user:
        resp = await client.get(session_url)
        session = await resp.json()
        assert session.get("user_email") == None
        await client.post(login_url, json={"email": user["email"], "password": user["raw_password"]})
        resp = await client.get(session_url)
        session = await resp.json()
        assert session.get("user_email") == user["email"]
        await client.post(logout_url)
        resp = await client.get(session_url)
        session = await resp.json()
        assert session.get("user_email") == None

async def test_me(client):
    # Tests that /me sets de user_email
    db = get_storage(client.app)
    session_url = "/session"
    delete_user_email_url = "/delete_user_email"
    me_url = client.app.router["get_my_profile"].url_for()
    async with LoggedUser(client) as user:
        await client.get(delete_user_email_url)
        resp = await client.get(session_url)
        session = await resp.json()
        assert session.get("user_email") == None
        await client.get(me_url)
        resp = await client.get(session_url)
        session = await resp.json()
        assert session.get("user_email") == user["email"]
    await db.delete_user(user)
