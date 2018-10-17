# pylint: disable=W0621
# TODO: W0611:Unused import ...
# pylint: disable=W0611
# W0612:Unused variable
# TODO: W0613:Unused argument ...
# pylint: disable=W0613
import pytest

import simcore_storage_sdk
import utils
from simcore_storage_sdk import HealthInfo

from aiohttp import web
from simcore_service_storage.settings import APP_CONFIG_KEY
from simcore_service_storage.rest import setup_rest
from simcore_service_storage.session import setup_session


@pytest.fixture
def client(loop, aiohttp_unused_port, aiohttp_client):
    app = web.Application()

    server_kwargs={'port': aiohttp_unused_port(), 'host': 'localhost'}
    # fake main
    app[APP_CONFIG_KEY] = { 'main': server_kwargs } # Fake config

    setup_session(app)
    setup_rest(app)

    assert "SECRET_KEY" in app[APP_CONFIG_KEY]

    cli = loop.run_until_complete( aiohttp_client(app, server_kwargs=server_kwargs) )
    return cli

async def test_health_check(client):
    resp = await client.get("/v0/")
    assert resp.status == 200

    envelope = await resp.json()
    data, error = [envelope[k] for k in ('data', 'error')]

    assert data
    assert not error

    assert data['name'] == 'simcore_service_storage'
    assert data['status'] == 'SERVICE_RUNNING'

async def test_action_check(client):
    QUERY = 'mguidon'
    ACTION = 'echo'
    FAKE = {
        'path_value': 'one',
        'query_value': 'two',
        'body_value': {
            'a': 33,
            'b': 45
        }
    }

    resp = await client.post("/v0/check/{}?data={}".format(ACTION, QUERY), json=FAKE)
    envelope = await resp.json()
    data, error = [envelope[k] for k in ('data', 'error')]

    assert resp.status == 200, str(envelope)
    assert data
    assert not error

    # TODO: validate response against specs

    assert data['path_value'] == ACTION
    assert data['query_value'] == QUERY
    #assert data['body_value'] == FAKE['body_value']











# def test_table_creation(postgres_service):
#     utils.create_tables(url=postgres_service)

# async def test_app(test_client):
#     last_access = -2
#     for _ in range(5):
#         res = await test_client.get("/v1/")
#         check = await res.json()
#         print(check["last_access"])
#         assert last_access < check["last_access"]
#         last_access = check["last_access"]

# #FIXME: still not working because of cookies
# async def test_api(test_server):
#     cfg = simcore_storage_sdk.Configuration()
#     cfg.host = cfg.host.format(
#         host=test_server.host,
#         port=test_server.port,
#         version="v1"
#     )
#     with utils.api_client(cfg) as api_client:
#         session = api_client.rest_client.pool_manager
#         for cookie in session.cookie_jar:
#             print(cookie.key)
#         api = simcore_storage_sdk.DefaultApi(api_client)
#         check = await api.health_check()
#         print(check)

#         assert isinstance(check, HealthInfo)
#         assert check.last_access == -1

#         #last_access = 0
#         for _ in range(5):
#             check = await api.health_check()
#             print(check)
#             #last_access < check.last_access
#             #FIXME: W0612: Unused variable 'last_access' (unused-variable)
#             last_access = check.last_access #pylint: disable=unused-variable

# def test_s3(s3_client):
#     bucket_name = "simcore-test"
#     assert s3_client.create_bucket(bucket_name)
#     assert s3_client.exists_bucket(bucket_name)
#     s3_client.remove_bucket(bucket_name, delete_contents=True)
#     assert not s3_client.exists_bucket(bucket_name)
