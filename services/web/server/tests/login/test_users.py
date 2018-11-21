# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import collections

import pytest
from aiohttp import web
from yarl import URL

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.rest_responses import unwrap_envelope
from simcore_service_webserver.db import setup_db, APP_DB_ENGINE_KEY
from simcore_service_webserver.login import setup_login
from simcore_service_webserver.rest import APP_OPENAPI_SPECS_KEY, setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.users import setup_users


from utils_assert import assert_status
from utils_login import LoggedUser
from utils_tokens import get_token_from_db, delete_all_tokens_from_db, create_token_in_db

API_VERSION = "v0"


@pytest.fixture
# , postgres_db):
def client(loop, aiohttp_client, aiohttp_unused_port, app_cfg):
    app = web.Application()
    port = app_cfg["main"]["port"] = aiohttp_unused_port()

    assert app_cfg["rest"]["version"] == API_VERSION
    assert API_VERSION in app_cfg["rest"]["location"]

    app_cfg["db"]["init_tables"] = True

    # fake config
    app[APP_CONFIG_KEY] = app_cfg

    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app, debug=True)
    setup_login(app)
    setup_users(app)

    client = loop.run_until_complete(aiohttp_client(app, server_kwargs={
        'port': port,
        'host': 'localhost'
    }))
    return client


@pytest.fixture
async def logged_user(client):
    """ adds a user in db registry and returns it """
    async with LoggedUser(client) as user:
        yield user

@pytest.fixture
async def tokens_db(logged_user, client):
    engine = client.app[APP_DB_ENGINE_KEY]
    yield engine
    await delete_all_tokens_from_db(engine)

import faker
from itertools import repeat
import random


@pytest.fixture
async def fake_tokens(logged_user, tokens_db):
    # See api/specs/webserver/v0/components/schemas/my.yaml
    # pylint: disable=E1101
    from faker.providers import lorem, misc
    fake = faker.Factory.create()
    fake.add_provider(lorem)
    fake.add_provider(lorem)

    all_tokens = []

    # TODO: automatically create data from oas!
    for _ in repeat(None, 50):
        # TODO: add tokens from other users
        data = {
            'service': fake.word(ext_word_list=None),
            'token_key': fake.md5(raw_output=False),
            'token_secret': fake.md5(raw_output=False)
        }
        row = await create_token_in_db( tokens_db,
            user_id = logged_user['id'],
            token_service = data['service'],
            token_data = data
        )
        all_tokens.append(data)
    return all_tokens




PREFIX = "/" + API_VERSION + "/my"

# test R on profile ----------------------------------------------------
async def test_get_profile(logged_user, client):
    url = client.app.router["get_my_profile"].url_for()
    assert str(url) == "/v0/my"

    resp = await client.get(url)
    payload = await resp.json()
    assert resp.status == 200, payload

    data, error = unwrap_envelope(payload)
    assert not error
    assert data

    assert data['login'] == logged_user["email"]
    assert data['gravatar_id']


# Test CRUD on tokens --------------------------------------------
RESOURCE_NAME = 'tokens'


# TODO: template for CRUD testing?
# TODO: create parametrize fixture with resource_name

async def test_create(client, logged_user, tokens_db):
    url = client.app.router["create_tokens"].url_for()
    assert '/v0/my/tokens' == str(url)

    token = {
        'service': "blackfynn",
        'token_key': '4k9lyzBTS',
        'token_secret': 'my secret'
    }

    resp = await client.post(url, json=token)
    payload = await resp.json()
    assert resp.status == 201, payload

    data, error = unwrap_envelope(payload)
    assert not error
    assert data

    db_token = await get_token_from_db(tokens_db, token_id=data)
    assert db_token['token_data'] == token
    assert db_token['user_id'] == logged_user["id"]


async def test_read(client, logged_user, tokens_db, fake_tokens):

    # list all
    url = client.app.router["list_tokens"].url_for()
    assert "/v0/my/tokens" == str(url)
    resp = await client.get(url)
    payload = await resp.json()
    assert resp.status == 200, payload

    data, error = unwrap_envelope(payload)
    assert not error
    assert data == fake_tokens

    # get one
    sid = fake_tokens[0]['service']

    url = client.app.router["get_token"].url_for(service=sid)
    assert "/v0/my/tokens/%s" % sid == str(url)
    resp = await client.get(url)
    payload = await resp.json()
    assert resp.status == 200, payload

    data, error = unwrap_envelope(payload)
    assert not error
    assert data == fake_tokens[0]


async def test_update(client):
    async with LoggedUser(client):
        async with NewToken({'service': 'blackfynn'}, client.app):

            url = client.app.router["update_token"].url_for(
                service='blackfynn')
            assert "/v0/my/tokens/blackfynn" == str(url)

            resp = await client.put(url, json={
                'token_secret': 'some completely new secret'
            })
            payload = await resp.json()
            assert resp.status == 200, payload

            # TODO: check db entry and field was update


async def test_delete(client):
    async with LoggedUser(client):
        async with NewToken({'service': 'blackfynn'}, client.app):
            url = client.app.router["delete_token"].url_for(
                service='blackfynn')
            assert "/v0/my/tokens/blackfynn" == str(url)

            resp = await client.delete(url)
            payload = await resp.json()

            assert resp.status == 204, payload
            assert not payload
