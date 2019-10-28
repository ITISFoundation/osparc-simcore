# pylint:disable=unused-import
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import logging
from copy import deepcopy
from urllib.parse import quote

import pytest
from aiohttp import web

from servicelib.application import create_safe_application
from servicelib.rest_responses import unwrap_envelope
from servicelib.rest_utils import extract_and_validate
from simcore_service_webserver.security_roles import UserRole
from utils_assert import assert_status
from utils_login import LoggedUser

API_VERSION = "v0"


# TODO: create a fake storage service here
@pytest.fixture()
def storage_server(loop, aiohttp_server, app_cfg):
    cfg = app_cfg["storage"]
    app = create_safe_application(cfg)

    async def _get_locs(request: web.Request):
        assert not request.has_body

        query = request.query
        assert query
        assert "user_id" in query

        assert query["user_id"], "Expected user id"
        return web.json_response({
            'data': [{"user_id": int(query["user_id"])}, ]
        })

    async def _get_filemeta(request: web.Request):
        assert not request.has_body

        query = request.query
        assert query
        assert "user_id" in query

        assert query["user_id"], "Expected user id"

        return web.json_response({
            'data': [{"filemeta": 42}, ]
        })

    async def _get_filtered_list(request: web.Request):
        assert not request.has_body

        query = request.query
        assert query
        assert "user_id" in query
        assert query["user_id"], "Expected user id"
        assert query["uuid_filter"], "expected a filter"

        return web.json_response({
            'data': [{"uuid_filter": query["uuid_filter"]}, ]
        })

    async def _get_datasets(request: web.Request):
        assert not request.has_body

        query = request.query
        assert query
        assert "user_id" in query

        assert query["user_id"], "Expected user id"

        return web.json_response({
            'data': [{"dataset_id": "asdf", "display_name" : "bbb"}, ]
        })

    async def _get_datasets_meta(request: web.Request):
        assert not request.has_body

        query = request.query
        assert query
        assert "user_id" in query

        assert query["user_id"], "Expected user id"

        return web.json_response({
            'data': [{"dataset_id": "asdf", "display_name" : "bbb"}, ]
        })

    storage_api_version = cfg['version']
    assert storage_api_version != API_VERSION, "backend service w/ different version as webserver entrypoint"

    app.router.add_get(f"/{storage_api_version}/locations" , _get_locs)
    app.router.add_get(f"/{storage_api_version}/locations/0/files/{{file_id}}/metadata", _get_filemeta)
    app.router.add_get(f"/{storage_api_version}/locations/0/files/metadata", _get_filtered_list)
    app.router.add_get(f"/{storage_api_version}/locations/0/datasets", _get_datasets)
    app.router.add_get(f"/{storage_api_version}/locations/0/datasets/{{dataset_id}}/metadata", _get_datasets_meta)

    assert cfg['host']=='localhost'


    server = loop.run_until_complete(aiohttp_server(app, port= cfg['port']))
    return server


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


#--------------------------------------------------------------------------
PREFIX = "/" + API_VERSION + "/storage"

@pytest.mark.parametrize("role,expected", [
    (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPOk),
    (UserRole.USER, web.HTTPOk),
    (UserRole.TESTER, web.HTTPOk),
])
async def test_get_storage_locations(client, storage_server, logged_user, role, expected):
    url = "/v0/storage/locations"
    assert url.startswith(PREFIX)

    resp = await client.get(url)
    data, error = await assert_status(resp, expected)

    if not error:
        assert len(data) == 1
        assert data[0]['user_id'] == logged_user['id']

@pytest.mark.parametrize("role,expected", [
    (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPOk),
    (UserRole.USER, web.HTTPOk),
    (UserRole.TESTER, web.HTTPOk),
])
async def test_get_datasets_metadata(client, storage_server, logged_user, role, expected):
    url = "/v0/storage/locations/0/datasets"
    assert url.startswith(PREFIX)

    _url = client.app.router["get_datasets_metadata"].url_for(location_id="0")

    assert url==str(_url)

    resp = await client.get(url)
    data, error = await assert_status(resp, expected)

    if not error:
        assert len(data) == 1
        assert data[0]["dataset_id"] == "asdf"


@pytest.mark.parametrize("role,expected", [
    (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPOk),
    (UserRole.USER, web.HTTPOk),
    (UserRole.TESTER, web.HTTPOk),
])
async def test_get_files_metadata_dataset(client, storage_server, logged_user, role, expected):
    url = "/v0/storage/locations/0/datasets/N:asdfsdf/metadata"
    assert url.startswith(PREFIX)

    _url = client.app.router["get_files_metadata_dataset"].url_for(location_id="0", dataset_id="N:asdfsdf")

    assert url==str(_url)

    resp = await client.get(url)
    data, error = await assert_status(resp, expected)

    if not error:
        assert len(data) == 1
        assert data[0]["dataset_id"] == "asdf"

@pytest.mark.parametrize("role,expected", [
    (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPOk),
    (UserRole.USER, web.HTTPOk),
    (UserRole.TESTER, web.HTTPOk),
])
async def test_storage_file_meta(client, storage_server, logged_user, role, expected):
    # tests redirect of path with quotes in path
    file_id = "a/b/c/d/e/dat"
    url = "/v0/storage/locations/0/files/{}/metadata".format(quote(file_id, safe=''))

    assert url.startswith(PREFIX)

    resp = await client.get(url)
    data, error = await assert_status(resp, expected)

    if not error:
        assert len(data) == 1
        assert data[0]['filemeta'] == 42


@pytest.mark.parametrize("role,expected", [
    (UserRole.ANONYMOUS, web.HTTPUnauthorized),
    (UserRole.GUEST, web.HTTPOk),
    (UserRole.USER, web.HTTPOk),
    (UserRole.TESTER, web.HTTPOk),
])
async def test_storage_list_filter(client, storage_server, logged_user, role, expected):
    # tests composition of 2 queries
    file_id = "a/b/c/d/e/dat"
    url = "/v0/storage/locations/0/files/metadata?uuid_filter={}".format(quote(file_id, safe=''))

    assert url.startswith(PREFIX)

    resp = await client.get(url)
    data, error = await assert_status(resp, expected)

    if not error:
        assert len(data) == 1
        assert data[0]['uuid_filter'] == file_id
