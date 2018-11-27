# pylint: disable=R0913
# pylint: disable=W0621
import os
from urllib.parse import quote

import pytest
from aiohttp import web

from simcore_service_storage.db import setup_db
from simcore_service_storage.dsm import setup_dsm
from simcore_service_storage.rest import setup_rest
from simcore_service_storage.session import setup_session
from simcore_service_storage.s3 import setup_s3
from simcore_service_storage.settings import APP_CONFIG_KEY, SIMCORE_S3_ID


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
def client(loop, aiohttp_unused_port, aiohttp_client, python27_path, postgres_service, minio_service, osparc_api_specs_dir):
    app = web.Application()

    main_cfg = {
        'port': aiohttp_unused_port(),
        'host': 'localhost',
        'python2': python27_path,
        "max_workers" : 4
    }
    rest_cfg = {
        'oas_repo': str(osparc_api_specs_dir), #'${OSPARC_SIMCORE_REPO_ROOTDIR}/api/specs',
        #oas_repo: http://localhost:8043/api/specs
    }
    postgres_cfg = postgres_service
    s3_cfg = minio_service


    # fake config
    app[APP_CONFIG_KEY] = {
        'main': main_cfg,
        'postgres' : postgres_cfg,
        's3' : s3_cfg,
        'rest': rest_cfg
    }

    #app.middlewares.append(dsm_middleware)

    setup_db(app)
    setup_session(app)
    setup_rest(app)
    setup_dsm(app)
    setup_s3(app)



    assert "SECRET_KEY" in app[APP_CONFIG_KEY]

    cli = loop.run_until_complete( aiohttp_client(app, server_kwargs=main_cfg) )
    return cli

async def test_health_check(client):
    resp = await client.get("/v0/")
    text = await resp.text()

    assert resp.status == 200, text

    payload = await resp.json()
    data, error = tuple( payload.get(k) for k in ('data', 'error') )

    assert data
    assert not error

    assert data['name'] == 'simcore_service_storage'
    assert data['status'] == 'SERVICE_RUNNING'

@pytest.mark.travis
async def test_locations(client):
    user_id = "0"

    resp = await client.get("/v0/locations?user_id={}".format(user_id))

    payload = await resp.json()
    assert resp.status == 200, str(payload)

    data, error = tuple( payload.get(k) for k in ('data', 'error') )

    assert len(data) == 2
    assert not error


async def test_s3_files_metadata(client, dsm_mockup_db):
    id_file_count, _id_name_map = parse_db(dsm_mockup_db)

    # list files for every user
    for _id in id_file_count:
        resp = await client.get("/v0/locations/0/files/metadata?user_id={}".format(_id))
        payload = await resp.json()
        assert resp.status == 200, str(payload)

        data, error = tuple( payload.get(k) for k in ('data', 'error') )
        assert not error
        assert len(data) == id_file_count[_id]

    # list files fileterd by uuid
    for d in dsm_mockup_db.keys():
        fmd = dsm_mockup_db[d]
        uuid_filter = os.path.join(fmd.project_id, fmd.node_id)
        resp = await client.get("/v0/locations/0/files/metadata?user_id={}&uuid_filter={}".format(fmd.user_id, quote(uuid_filter, safe='')))
        payload = await resp.json()
        assert resp.status == 200, str(payload)

        data, error = tuple( payload.get(k) for k in ('data', 'error') )
        assert not error
        for d in data:
            assert os.path.join(d['project_id'], d['node_id']) == uuid_filter

async def test_s3_file_metadata(client, dsm_mockup_db):
    # go through all files and get them
    for d in dsm_mockup_db.keys():
        fmd = dsm_mockup_db[d]
        resp = await client.get("/v0/locations/0/files/{}/metadata?user_id={}".format(quote(fmd.file_uuid, safe=''), fmd.user_id))
        payload = await resp.json()
        assert resp.status == 200, str(payload)

        data, error = tuple( payload.get(k) for k in ('data', 'error') )
        assert not error
        assert data

async def test_download_link(client, dsm_mockup_db):
    for d in dsm_mockup_db.keys():
        fmd = dsm_mockup_db[d]
        resp = await client.get("/v0/locations/0/files/{}?user_id={}".format(quote(fmd.file_uuid, safe=''), fmd.user_id))
        payload = await resp.json()
        assert resp.status == 200, str(payload)

        data, error = tuple( payload.get(k) for k in ('data', 'error') )
        assert not error
        assert data

async def test_upload_link(client, dsm_mockup_db):
    for d in dsm_mockup_db.keys():
        fmd = dsm_mockup_db[d]
        resp = await client.put("/v0/locations/0/files/{}?user_id={}".format(quote(fmd.file_uuid, safe=''), fmd.user_id))
        payload = await resp.json()
        assert resp.status == 200, str(payload)

        data, error = tuple( payload.get(k) for k in ('data', 'error') )
        assert not error
        assert data

@pytest.mark.travis
async def test_copy(client, dsm_mockup_db, datcore_testbucket):
    # copy N files
    N = 2
    counter = 0
    for d in dsm_mockup_db.keys():
        fmd = dsm_mockup_db[d]
        source_uuid = fmd.file_uuid
        datcore_uuid = os.path.join(datcore_testbucket, fmd.file_name)
        resp = await client.put("/v0/locations/1/files/{}?user_id={}&extra_location={}&extra_source={}".format(quote(datcore_uuid, safe=''),
            fmd.user_id, SIMCORE_S3_ID, quote(source_uuid, safe='')))
        payload = await resp.json()
        assert resp.status == 200, str(payload)

        data, error = tuple( payload.get(k) for k in ('data', 'error') )
        assert not error
        assert data

        counter = counter + 1
        if counter == N:
            break

    # list files for every user
    user_id = "0"
    resp = await client.get("/v0/locations/1/files/metadata?user_id={}".format(user_id))
    payload = await resp.json()
    assert resp.status == 200, str(payload)

    data, error = tuple( payload.get(k) for k in ('data', 'error') )
    assert not error
    assert len(data) == 2 + N

async def test_delete_file(client, dsm_mockup_db):
    id_file_count, _id_name_map = parse_db(dsm_mockup_db)

    for d in dsm_mockup_db.keys():
        fmd = dsm_mockup_db[d]
        resp = await client.delete("/v0/locations/0/files/{}?user_id={}".format(quote(fmd.file_uuid, safe=''), fmd.user_id))
        payload = await resp.json()
        assert resp.status == 200, str(payload)

        data, error = tuple( payload.get(k) for k in ('data', 'error') )
        assert not error
        assert not data

    for _id in id_file_count:
        resp = await client.get("/v0/locations/0/files/metadata?user_id={}".format(_id))
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
