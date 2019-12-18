# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import collections
import random
from copy import deepcopy
from itertools import repeat
from unittest.mock import MagicMock

import faker
import pytest
from aiohttp import web
from aiopg.sa.connection import SAConnection
from psycopg2 import OperationalError
from yarl import URL

from servicelib.application import create_safe_application
from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.rest_responses import unwrap_envelope
from simcore_service_webserver.db import APP_DB_ENGINE_KEY, setup_db
from simcore_service_webserver.login import setup_login
from simcore_service_webserver.rest import APP_OPENAPI_SPECS_KEY, setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.security_roles import UserRole
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.users import setup_users
from utils_assert import assert_status
from utils_login import LoggedUser
from utils_tokens import (create_token_in_db, delete_all_tokens_from_db,
                          get_token_from_db)

API_VERSION = "v0"


@pytest.fixture
def client(loop, aiohttp_client, app_cfg, postgres_service):
    cfg = deepcopy(app_cfg)

    port = cfg["main"]["port"]

    assert cfg["rest"]["version"] == API_VERSION
    assert API_VERSION in cfg["rest"]["location"]

    cfg["db"]["init_tables"] = True # inits postgres_service

    # fake config
    app = create_safe_application(cfg)

    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_login(app)
    setup_users(app)

    client = loop.run_until_complete(aiohttp_client(app, server_kwargs={
        'port': port,
        'host': 'localhost'
    }))
    return client


# WARNING: pytest-asyncio and pytest-aiohttp are not compatible
#
# https://github.com/aio-libs/pytest-aiohttp/issues/8#issuecomment-405602020
# https://github.com/pytest-dev/pytest-asyncio/issues/76
#

@pytest.fixture
async def logged_user(client, role: UserRole):
    """ adds a user in db and logs in with client

    NOTE: role fixture is defined as a parametrization below
    """
    async with LoggedUser(
        client,
        {"role": role.name},
        check_if_succeeds = role!=UserRole.ANONYMOUS
    ) as user:
        yield user


@pytest.fixture
async def tokens_db(logged_user, client):
    engine = client.app[APP_DB_ENGINE_KEY]
    yield engine
    await delete_all_tokens_from_db(engine)


@pytest.fixture
async def fake_tokens(logged_user, tokens_db):
    # pylint: disable=E1101
    from faker.providers import lorem, misc

    fake = faker.Factory.create()
    fake.seed(4567) # Always the same fakes
    fake.add_provider(lorem)
    fake.add_provider(lorem)

    all_tokens = []

    # TODO: automatically create data from oas!
    # See api/specs/webserver/v0/components/schemas/me.yaml
    for _ in repeat(None, 5):
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


#--------------------------------------------------------------------------
PREFIX = "/" + API_VERSION + "/me"

@pytest.mark.parametrize("role,expected", [
    (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPOk),
    (UserRole.USER, web.HTTPOk),
    (UserRole.TESTER, web.HTTPOk),
])
async def test_get_profile(logged_user, client, role, expected):
    url = client.app.router["get_my_profile"].url_for()
    assert str(url) == "/v0/me"

    resp = await client.get(url)
    data, error = await assert_status(resp, expected)

    if not error:
        assert data['login'] == logged_user["email"]
        assert data['gravatar_id']
        assert data['first_name'] == logged_user["name"]
        assert data['last_name'] == ""
        assert data['role'] == role.name.capitalize()

@pytest.mark.parametrize("role,expected", [
    (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPForbidden),
    (UserRole.USER, web.HTTPNoContent),
    (UserRole.TESTER, web.HTTPNoContent),
])
async def test_update_profile(logged_user, client, role, expected):
    url = client.app.router["update_my_profile"].url_for()
    assert str(url) == "/v0/me"

    resp = await client.put(url, json={"last_name": "Foo"})
    _, error = await assert_status(resp, expected)

    if not error:
        resp = await client.get(url)
        data, _ = await assert_status(resp, web.HTTPOk)

        assert data['first_name'] == logged_user["name"]
        assert data['last_name'] == "Foo"
        assert data['role'] == role.name.capitalize()



# Test CRUD on tokens --------------------------------------------
# TODO: template for CRUD testing?
# TODO: create parametrize fixture with resource_name

RESOURCE_NAME = 'tokens'
PREFIX = "/" + API_VERSION + "/me/" + RESOURCE_NAME



@pytest.mark.parametrize("role,expected", [
    (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPForbidden),
    (UserRole.USER, web.HTTPCreated),
    (UserRole.TESTER, web.HTTPCreated),
])
async def test_create_token(client, logged_user, tokens_db, role, expected):
    url = client.app.router["create_tokens"].url_for()
    assert '/v0/me/tokens' == str(url)

    token = {
        'service': "blackfynn",
        'token_key': '4k9lyzBTS',
        'token_secret': 'my secret'
    }

    resp = await client.post(url, json=token)
    data, error = await assert_status(resp, expected)
    if not error:
        db_token = await get_token_from_db(tokens_db, token_data=token)
        assert db_token['token_data'] == token
        assert db_token['user_id'] == logged_user["id"]


@pytest.mark.parametrize("role,expected", [
    (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPForbidden),
    (UserRole.USER, web.HTTPOk),
    (UserRole.TESTER, web.HTTPOk),
])
async def test_read_token(client, logged_user, tokens_db, fake_tokens, role, expected):
    # list all
    url = client.app.router["list_tokens"].url_for()
    assert "/v0/me/tokens" == str(url)

    resp = await client.get(url)
    data, error = await assert_status(resp, expected)

    if not error:
        expected_token = random.choice(fake_tokens)
        sid = expected_token['service']

        # get one
        url = client.app.router["get_token"].url_for(service=sid)
        assert "/v0/me/tokens/%s" % sid == str(url)
        resp = await client.get(url)

        data, error = await assert_status(resp, expected)

        assert data == expected_token, "list and read item are both read operations"


@pytest.mark.parametrize("role,expected", [
    (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPForbidden),
    (UserRole.USER, web.HTTPNoContent),
    (UserRole.TESTER, web.HTTPNoContent),
])
async def test_update_token(client, logged_user, tokens_db, fake_tokens, role, expected):

    selected = random.choice(fake_tokens)
    sid = selected['service']

    url = client.app.router["get_token"].url_for(service=sid)
    assert "/v0/me/tokens/%s" % sid == str(url)

    resp = await client.put(url, json={
        'token_secret': 'some completely new secret'
    })
    data, error = await assert_status(resp, expected)

    if not error:
        # check in db
        token_in_db = await get_token_from_db(tokens_db, token_service=sid)

        assert token_in_db['token_data']['token_secret'] == 'some completely new secret'
        assert token_in_db['token_data']['token_secret'] != selected['token_secret']

        selected['token_secret'] = 'some completely new secret'
        assert token_in_db['token_data'] == selected


@pytest.mark.parametrize("role,expected", [
    (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPForbidden),
    (UserRole.USER, web.HTTPNoContent),
    (UserRole.TESTER, web.HTTPNoContent),
])
async def test_delete_token(client, logged_user, tokens_db, fake_tokens, role, expected):
    sid = fake_tokens[0]['service']

    url = client.app.router["delete_token"].url_for(service=sid)
    assert "/v0/me/tokens/%s" % sid == str(url)

    resp = await client.delete(url)

    data, error = await assert_status(resp, expected)

    if not error:
        assert not (await get_token_from_db(tokens_db, token_service=sid))


## BUG FIXES #######################################################

@pytest.fixture
def mock_failing_connection(mocker) -> MagicMock:
    """
        async with engine.acquire() as conn:
            await conn.execute(query)  --> will raise OperationalError
    """
    # See http://initd.org/psycopg/docs/module.html
    conn_execute = mocker.patch.object(SAConnection, "execute")
    conn_execute.side_effect=OperationalError("MOCK: server closed the connection unexpectedly")
    return conn_execute

@pytest.mark.parametrize("role,expected", [
    (UserRole.USER, web.HTTPServiceUnavailable),
])
async def test_get_profile_with_failing_db_connection(logged_user, client,
    mock_failing_connection: MagicMock,
    role: UserRole,
    expected: web.HTTPException):
    """
        Reproduces issue https://github.com/ITISFoundation/osparc-simcore/pull/1160

        A logged user fails to get profie because though authentication because

        i.e. conn.execute(query) will raise psycopg2.OperationalError: server closed the connection unexpectedly

        ISSUES: #880, #1160
    """
    url = client.app.router["get_my_profile"].url_for()
    assert str(url) == "/v0/me"

    resp = await client.get(url)

    NUM_RETRY = 3
    assert mock_failing_connection.call_count == NUM_RETRY, "Expected mock failure raised in AuthorizationPolicy.authorized_userid after severals"

    data, error = await assert_status(resp, expected)
