# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
import yaml
from aiohttp import web
from faker import Faker

from simcore_service_webserver.application_keys import (APP_CONFIG_KEY,
                                                        APP_DB_ENGINE_KEY)
from simcore_service_webserver.db import pg_engine
from simcore_service_webserver.db_models import (UserRole, UserStatus,
                                                 metadata, users)
from simcore_service_webserver.security import (authorized_userid,
                                                check_credentials, forget,
                                                generate_password_hash,
                                                is_anonymous, login_required,
                                                remember, setup_security)
from simcore_service_webserver.session import setup_session

DNS = "postgresql://{user}:{password}@{host}:{port}/{database}"

@pytest.fixture(scope="session")
def here():
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

@pytest.fixture(scope="session")
def app_cfg(here):
    cfg_path = here / "config.yaml"
    with cfg_path.open() as f:
        cfg = yaml.safe_load(f)
    return cfg


@pytest.fixture(scope="session")
def postgres_db(app_cfg):
    # Configures db and initializes tables
    # uses syncrounous engine for that

    cfg = app_cfg["postgres"]
    url = DNS.format(**cfg)

    engine = sa.create_engine(url, isolation_level="AUTOCOMMIT")
    metadata.create_all(bind=engine, tables=[users,], checkfirst=True)

    yield engine

    import pdb; pdb.set_trace()

    metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="session")
def fake_users_db(postgres_db):
    data = [
        {
            "name": "bizzy",
            "email": "bizzy@foo.com",
            "password_hash": generate_password_hash("z43"),
            "status": UserStatus.ACTIVE,
            "role": UserRole.USER,
        },
        {
            "name": "pcrespov",
            "email": "pcrespov@foo.com",
            "password_hash": generate_password_hash("secret"),
            "status": UserStatus.ACTIVE,
            "role": UserRole.ADMIN,
        }
    ]

    # NOTE: if data, then
    with postgres_db.connect() as cnx:
        cnx.execute(users.insert(), data)

    return data


@pytest.fixture
def server(loop, aiohttp_server, fake_users_db, app_cfg):
    app = web.Application()

    assert fake_users_db

    app[APP_CONFIG_KEY] = app_cfg

    app.cleanup_ctx.append(pg_engine) # light alternative to avoid _init_db
    setup_session(app)
    setup_security(app)

    async def _check(request):
        import pdb; pdb.set_trace()
        is_logged = not await is_anonymous(request)
        return web.json_response({
            'message': 'hoi there',
            'is_logged': is_logged
        })

    async def _login(request):
        import pdb; pdb.set_trace()
        body = await request.json()

        engine = request.app[APP_DB_ENGINE_KEY]

        if not await check_credentials(engine, body.get('email'), body.get('password')):
            raise web.HTTPUnauthorized(content_type='application/json')

        response = web.HTTPNoContent(content_type='application/json')
        remember(request, response, body.get('email'))
        raise response


    @login_required
    async def _who(request):
        import pdb; pdb.set_trace()

        user_id = await authorized_userid(request)

        engine = request.app[APP_DB_ENGINE_KEY]
        async with engine.acquire() as cnx:
            query = users.select().where(users.c.user_id == user_id)
            ret = await cnx.execute(query)
            user = await ret.fetchone()

        # returns
        return web.json_response(data={ k:user[k]
            for k in ["name", "email", "status", "role", "reated_at", "created_ip"] } )

    @login_required
    async def _logout(request):
        import pdb; pdb.set_trace()
        response = web.HTTPNoContent(content_type='application/json')
        forget(request, response)
        raise response


    app.router.add_get("/", _check, name="check")
    app.router.add_post("/login", _login, name="login")
    app.router.add_get("/me", _who, name="me")
    app.router.add_get("/logout", _logout, name="logout")

    server = loop.run_until_complete( aiohttp_server(app))
    return server


@pytest.fixture
def clients(loop, aiohttp_client, server, fake_users_db):
    pcrespov = loop.run_until_complete( aiohttp_client(server) )
    bizzy = loop.run_until_complete( aiohttp_client(server) )

    return pcrespov, bizzy


async def test_it(clients, fake_users_db):
    pcrespov, bizzy = clients

    import pdb; pdb.set_trace()
    resp = await pcrespov.get("/")
    payload = await resp.json()

    assert resp.status == 200
    assert payload.get("message") == "hoi there"
    assert not payload["is_logged"]

    import pdb; pdb.set_trace()
    resp = await pcrespov.post("/login", json={
        'email': 'pcrespov@foo.com',
        'password': 'secret'
    })
    assert resp.status == 204

    import pdb; pdb.set_trace()
    resp = await pcrespov.get("/")
    payload = await resp.json()

    assert resp.status == 200
    assert payload["is_logged"]

    resp = await pcrespov.get("/me")
    payload = await resp.json()

    print(payload)
    assert payload['email'] == 'pcrespov@foo.com'


    import pdb; pdb.set_trace()
    assert resp.status == 200
    assert payload.get("message") == "hoi there"
    assert not payload["is_logged"]



    resp = await bizzy.get("/")
    payload = await resp.json()
    assert resp.status == 200
    assert payload.get("message") == "hoi there"
    assert not payload["is_logged"]
