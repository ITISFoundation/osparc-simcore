# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=no-name-in-module

import json
import os
import sys
from asyncio import Future
from copy import deepcopy
from pathlib import Path
from urllib.parse import quote

import pytest
from aiohttp import web

from simcore_service_storage.db import setup_db
from simcore_service_storage.dsm import (APP_DSM_KEY, DataStorageManager,
                                         setup_dsm)
from simcore_service_storage.rest import setup_rest
from simcore_service_storage.s3 import setup_s3
from simcore_service_storage.settings import APP_CONFIG_KEY, SIMCORE_S3_ID
from utils import BUCKET_NAME, USER_ID, has_datcore_tokens
from utils_assert import assert_status
from utils_project import clone_project_data

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

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
def client(loop, aiohttp_unused_port, aiohttp_client, postgres_service, minio_service, osparc_api_specs_dir):
    app = web.Application()

    api_token = os.environ.get("BF_API_KEY", "none")
    api_secret = os.environ.get("BF_API_SECRET", "none")

    main_cfg = {
        'port': aiohttp_unused_port(),
        'host': 'localhost',
        "max_workers" : 4,
        "testing" : True,
        "test_datcore" : { 'api_token' : api_token, 'api_secret' : api_secret}
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

    setup_db(app)
    setup_rest(app)
    setup_dsm(app)
    setup_s3(app)

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

async def test_locations(client):
    user_id = USER_ID

    resp = await client.get("/v0/locations?user_id={}".format(user_id))

    payload = await resp.json()
    assert resp.status == 200, str(payload)

    data, error = tuple( payload.get(k) for k in ('data', 'error') )

    _locs = 2 if has_datcore_tokens() else  1
    assert len(data) == _locs
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

async def test_copy(client, dsm_mockup_db, datcore_structured_testbucket):
    if not has_datcore_tokens():
        return
    # copy N files
    N = 2
    counter = 0
    for d in dsm_mockup_db.keys():
        fmd = dsm_mockup_db[d]
        source_uuid = fmd.file_uuid
        datcore_id = datcore_structured_testbucket['coll1_id']
        resp = await client.put("/v0/locations/1/files/{}?user_id={}&extra_location={}&extra_source={}".format(quote(datcore_id, safe=''),
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
    user_id = USER_ID
    resp = await client.get("/v0/locations/1/files/metadata?user_id={}&uuid_filter={}".format(user_id, BUCKET_NAME))
    payload = await resp.json()
    assert resp.status == 200, str(payload)

    data, error = tuple( payload.get(k) for k in ('data', 'error') )
    assert not error
    assert len(data) > N

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

def get_project_with_data():
    projects = []
    with open(current_dir / "data/projects_with_data.json") as fp:
        projects = json.load(fp)

    # TODO: add schema validation
    return projects

@pytest.mark.parametrize("project_name,project", [ (prj['name'], prj) for prj in get_project_with_data()])
async def test_create_and_delete_folders_from_project(client, dsm_mockup_db, project_name, project, mocker):
    source_project = project
    destination_project, nodes_map = clone_project_data(source_project)

    dsm = client.app[APP_DSM_KEY]
    mock_dsm = mocker.patch.object(dsm,"copy_file_datcore_s3")
    mock_dsm.return_value = Future()
    mock_dsm.return_value.set_result("Howdie")


    # CREATING
    url = client.app.router["copy_folders_from_project"].url_for().with_query(user_id="1")
    resp = await client.post(url, json={
        'source':source_project,
        'destination': destination_project,
        'nodes_map': nodes_map
    })

    data, _error = await assert_status(resp, expected_cls=web.HTTPCreated)

    # data should be equal to the destination project, and all store entries should point to simcore.s3
    for key in data:
        if key!="workbench":
            assert data[key] == destination_project[key]
        else:
            for _node_id, node in data[key].items():
                if 'outputs' in node:
                    for _o_id, o in node['outputs'].items():
                        if 'store' in o:
                            assert o['store'] == SIMCORE_S3_ID

    # DELETING
    project_id = data['uuid']
    url = client.app.router["delete_folders_of_project"].url_for(folder_id=project_id).with_query(user_id="1")
    resp = await client.delete(url)

    await assert_status(resp, expected_cls=web.HTTPNoContent)

async def test_s3_datasets_metadata(client):
    url = client.app.router["get_datasets_metadata"].url_for(location_id=str(SIMCORE_S3_ID)).with_query(user_id="21")
    resp = await client.get(url)
    payload = await resp.json()
    assert resp.status == 200, str(payload)
    data, error = tuple( payload.get(k) for k in ('data', 'error') )
    assert not error

async def test_s3_files_datasets_metadata(client):
    url = client.app.router["get_files_metadata_dataset"].url_for(location_id=str(SIMCORE_S3_ID), dataset_id="aa").with_query(user_id="21")
    resp = await client.get(url)
    payload = await resp.json()
    assert resp.status == 200, str(payload)
    data, error = tuple( payload.get(k) for k in ('data', 'error') )
    assert not error
