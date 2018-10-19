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
from simcore_service_storage.db import setup_db
from simcore_service_storage.middlewares import dsm_middleware

from urllib.parse import quote

def parse_db(dsm_mockup_db):
    id_name_map = {}
    id_file_count = {}
    for d in dsm_mockup_db.keys():
        md = dsm_mockup_db[d]
        if not md.user_id in id_name_map:
            id_name_map[md.user_id] = md.user_name
            id_file_count[md.user_id] = 1
        else:
            id_file_count[md.user_id] = id_file_count[md.user_id] + 1

    return id_file_count, id_name_map

@pytest.fixture
def client(loop, aiohttp_unused_port, aiohttp_client, python27_exec, postgres_service, minio_service):
    app = web.Application()

    server_kwargs={'port': aiohttp_unused_port(), 'host': 'localhost', 'python2' : python27_exec }

    postgres_kwargs = postgres_service

    s3_kwargs = minio_service

    # fake main
    app[APP_CONFIG_KEY] = { 'main': server_kwargs, 'postgres' : postgres_kwargs, "s3" : s3_kwargs } # Fake config

    app.middlewares.append(dsm_middleware)

    setup_db(app)
    setup_session(app)
    setup_rest(app)

    assert "SECRET_KEY" in app[APP_CONFIG_KEY]

    cli = loop.run_until_complete( aiohttp_client(app, server_kwargs=server_kwargs) )
    return cli

async def test_health_check(client):
    resp = await client.get("/v0/")
    assert resp.status == 200

    payload = await resp.json()
    data, error = tuple( payload.get(k) for k in ('data', 'error') )

    assert data
    assert not error

    assert data['name'] == 'simcore_service_storage'
    assert data['status'] == 'SERVICE_RUNNING'


async def test_locations(client):
    resp = await client.get("/v0/locations")

    payload = await resp.json()
    assert resp.status == 200, str(payload)

    data, error = tuple( payload.get(k) for k in ('data', 'error') )

    assert len(data) == 2
    assert not error


async def test_s3_files_metadata(client, dsm_mockup_db):
    id_file_count, _id_name_map = parse_db(dsm_mockup_db)

    # list files for every user
    for _id in id_file_count:
        resp = await client.get("/v0/0/files/metadata?user_id={}".format(_id))
        payload = await resp.json()
        assert resp.status == 200, str(payload)

        data, error = tuple( payload.get(k) for k in ('data', 'error') )
        assert not error
        assert len(data) == id_file_count[_id]

async def test_s3_file_metadata(client, dsm_mockup_db):
    # go through all files and get them
    for d in dsm_mockup_db.keys():
        fmd = dsm_mockup_db[d]
        resp = await client.get("/v0/0/files/{}/metadata?user_id={}".format(quote(fmd.file_uuid, safe=''), fmd.user_id))
        payload = await resp.json()
        assert resp.status == 200, str(payload)

        data, error = tuple( payload.get(k) for k in ('data', 'error') )
        assert not error
        assert data

async def test_download_link(client, dsm_mockup_db):
    for d in dsm_mockup_db.keys():
        fmd = dsm_mockup_db[d]
        resp = await client.get("/v0/0/files/{}?user_id={}".format(quote(fmd.file_uuid, safe=''), fmd.user_id))
        payload = await resp.json()
        assert resp.status == 200, str(payload)

        data, error = tuple( payload.get(k) for k in ('data', 'error') )
        print(data)
        assert not error
        assert data

async def test_upload_link(client, dsm_mockup_db):
    for d in dsm_mockup_db.keys():
        fmd = dsm_mockup_db[d]
        resp = await client.put("/v0/0/files/{}?user_id={}".format(quote(fmd.file_uuid, safe=''), fmd.user_id))
        payload = await resp.json()
        assert resp.status == 200, str(payload)

        data, error = tuple( payload.get(k) for k in ('data', 'error') )
        print(data)
        assert not error
        assert data

async def test_delete_file(client, dsm_mockup_db):
    id_file_count, _id_name_map = parse_db(dsm_mockup_db)


    for d in dsm_mockup_db.keys():
        fmd = dsm_mockup_db[d]
        resp = await client.delete("/v0/0/files/{}?user_id={}".format(quote(fmd.file_uuid, safe=''), fmd.user_id))
        payload = await resp.json()
        assert resp.status == 200, str(payload)

        data, error = tuple( payload.get(k) for k in ('data', 'error') )
        assert not error
        assert not data

    for _id in id_file_count:
        resp = await client.get("/v0/0/files/metadata?user_id={}".format(_id))
        payload = await resp.json()
        assert resp.status == 200, str(payload)

        data, error = tuple( payload.get(k) for k in ('data', 'error') )
        assert not error
        assert len(data) == 0


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
    payload = await resp.json()
    data, error = tuple( payload.get(k) for k in ('data', 'error') )

    assert resp.status == 200, str(payload)
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
