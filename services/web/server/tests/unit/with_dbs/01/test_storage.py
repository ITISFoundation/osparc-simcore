# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import asyncio
from collections.abc import Awaitable, Callable
from urllib.parse import quote

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from faker import Faker
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.aiohttp import status
from servicelib.aiohttp.application import create_safe_application
from simcore_postgres_database.models.users import UserRole

API_VERSION = "v0"


# TODO: create a fake storage service here
@pytest.fixture()
def storage_server(
    event_loop: asyncio.AbstractEventLoop,
    aiohttp_server: Callable[..., Awaitable[TestServer]],
    app_environment: EnvVarsDict,
    storage_test_server_port: int,
) -> TestServer:
    async def _get_locs(request: web.Request):
        assert not request.can_read_body

        query = request.query
        assert query
        assert "user_id" in query

        assert query["user_id"], "Expected user id"
        return web.json_response(
            {
                "data": [
                    {"user_id": int(query["user_id"])},
                ]
            }
        )

    async def _post_sync_meta_data(request: web.Request):
        assert not request.can_read_body

        query = request.query
        assert query
        assert "dry_run" in query

        assert query["dry_run"] == "true"
        return web.json_response(
            {
                "data": {"removed": []},
            }
        )

    async def _get_filemeta(request: web.Request):
        assert not request.can_read_body

        query = request.query
        assert query
        assert "user_id" in query

        assert query["user_id"], "Expected user id"

        return web.json_response(
            {
                "data": [
                    {"filemeta": 42},
                ]
            }
        )

    async def _get_filtered_list(request: web.Request):
        assert not request.can_read_body

        query = request.query
        assert query
        assert "user_id" in query
        assert query["user_id"], "Expected user id"
        assert query["uuid_filter"], "expected a filter"

        return web.json_response(
            {
                "data": [
                    {"uuid_filter": query["uuid_filter"]},
                ]
            }
        )

    async def _get_datasets(request: web.Request):
        assert not request.can_read_body

        query = request.query
        assert query
        assert "user_id" in query

        assert query["user_id"], "Expected user id"

        return web.json_response(
            {
                "data": [
                    {"dataset_id": "asdf", "display_name": "bbb"},
                ]
            }
        )

    async def _get_datasets_meta(request: web.Request):
        assert not request.can_read_body

        query = request.query
        assert query
        assert "user_id" in query

        assert query["user_id"], "Expected user id"

        return web.json_response(
            {
                "data": [
                    {"dataset_id": "asdf", "display_name": "bbb"},
                ]
            }
        )

    storage_api_version = app_environment["STORAGE_VTAG"]
    storage_port = int(app_environment["STORAGE_PORT"])
    assert storage_port == storage_test_server_port

    assert (
        storage_api_version != API_VERSION
    ), "backend service w/ different version as webserver entrypoint"

    app = create_safe_application()
    app.router.add_get(f"/{storage_api_version}/locations", _get_locs)
    app.router.add_post(
        f"/{storage_api_version}/locations/0:sync", _post_sync_meta_data
    )
    app.router.add_get(
        f"/{storage_api_version}/locations/0/files/{{file_id}}/metadata", _get_filemeta
    )
    app.router.add_get(
        f"/{storage_api_version}/locations/0/files/metadata", _get_filtered_list
    )
    app.router.add_get(f"/{storage_api_version}/locations/0/datasets", _get_datasets)
    app.router.add_get(
        f"/{storage_api_version}/locations/0/datasets/{{dataset_id}}/metadata",
        _get_datasets_meta,
    )

    return event_loop.run_until_complete(aiohttp_server(app, port=storage_port))


# --------------------------------------------------------------------------
PREFIX = "/" + API_VERSION + "/storage"


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_200_OK),
        (UserRole.USER, status.HTTP_200_OK),
        (UserRole.TESTER, status.HTTP_200_OK),
    ],
)
async def test_list_storage_locations(
    client: TestClient, storage_server: TestServer, logged_user, expected
):
    url = "/v0/storage/locations"
    assert url.startswith(PREFIX)

    resp = await client.get(url, params={"user_id": logged_user["id"]})
    data, error = await assert_status(resp, expected)

    if not error:
        assert len(data) == 1
        assert data[0]["user_id"] == logged_user["id"]


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_403_FORBIDDEN),
        (UserRole.USER, status.HTTP_403_FORBIDDEN),
        (UserRole.TESTER, status.HTTP_403_FORBIDDEN),
        (UserRole.ADMIN, status.HTTP_200_OK),
    ],
)
async def test_sync_file_meta_table(
    client: TestClient, storage_server: TestServer, logged_user, expected
):
    url = "/v0/storage/locations/0:sync"
    assert url.startswith(PREFIX)

    resp = await client.post(url, params={"dry_run": "true"})
    data, error = await assert_status(resp, expected)

    if not error:
        # the test of the functionality is already done in storage
        assert "removed" in data
        assert not data["removed"]


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_200_OK),
        (UserRole.USER, status.HTTP_200_OK),
        (UserRole.TESTER, status.HTTP_200_OK),
    ],
)
async def test_list_datasets_metadata(
    client: TestClient, storage_server: TestServer, logged_user, expected
):
    url = "/v0/storage/locations/0/datasets"
    assert url.startswith(PREFIX)

    _url = client.app.router["list_datasets_metadata"].url_for(location_id="0")

    assert url == str(_url)

    resp = await client.get(url, params={"user_id": logged_user["id"]})
    data, error = await assert_status(resp, expected)

    if not error:
        assert len(data) == 1
        assert data[0]["dataset_id"] == "asdf"


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_200_OK),
        (UserRole.USER, status.HTTP_200_OK),
        (UserRole.TESTER, status.HTTP_200_OK),
    ],
)
async def test_get_files_metadata_dataset(
    client: TestClient, storage_server: TestServer, logged_user, expected
):
    url = "/v0/storage/locations/0/datasets/N:asdfsdf/metadata"
    assert url.startswith(PREFIX)

    _url = client.app.router["get_files_metadata_dataset"].url_for(
        location_id="0", dataset_id="N:asdfsdf"
    )

    assert url == str(_url)

    resp = await client.get(url, params={"user_id": logged_user["id"]})
    data, error = await assert_status(resp, expected)

    if not error:
        assert len(data) == 1
        assert data[0]["dataset_id"] == "asdf"


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_200_OK),
        (UserRole.USER, status.HTTP_200_OK),
        (UserRole.TESTER, status.HTTP_200_OK),
    ],
)
async def test_storage_file_meta(
    client: TestClient, storage_server: TestServer, logged_user, expected, faker: Faker
):
    # tests redirect of path with quotes in path
    file_id = f"{faker.uuid4()}/{faker.uuid4()}/a/b/c/d/e/dat"
    quoted_file_id = quote(file_id, safe="")
    url = f"/v0/storage/locations/0/files/{quoted_file_id}/metadata"

    assert url.startswith(PREFIX)

    resp = await client.get(url, params={"user_id": logged_user["id"]})
    data, error = await assert_status(resp, expected)

    if not error:
        assert len(data) == 1
        assert data[0]["filemeta"] == 42


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_200_OK),
        (UserRole.USER, status.HTTP_200_OK),
        (UserRole.TESTER, status.HTTP_200_OK),
    ],
)
async def test_storage_list_filter(
    client: TestClient, storage_server: TestServer, logged_user, expected
):
    # tests composition of 2 queries
    file_id = "a/b/c/d/e/dat"
    url = "/v0/storage/locations/0/files/metadata?uuid_filter={}".format(
        quote(file_id, safe="")
    )

    assert url.startswith(PREFIX)

    resp = await client.get(url, params={"user_id": logged_user["id"]})
    data, error = await assert_status(resp, expected)

    if not error:
        assert len(data) == 1
        assert data[0]["uuid_filter"] == file_id
