# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import Callable
from typing import Any
from urllib.parse import quote

import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
from fastapi_pagination.cursor import CursorPage
from models_library.api_schemas_long_running_tasks.tasks import TaskGet
from models_library.api_schemas_rpc_async_jobs.async_jobs import AsyncJobGet, AsyncJobId
from models_library.api_schemas_storage.storage_schemas import (
    DatasetMetaDataGet,
    FileLocation,
    FileMetaDataGet,
    FileUploadSchema,
    PathMetaDataGet,
)
from models_library.projects_nodes_io import LocationID, StorageFileID
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from servicelib.aiohttp import status
from servicelib.rabbitmq.rpc_interfaces.async_jobs.async_jobs import (
    submit_job,
)
from simcore_postgres_database.models.users import UserRole

API_VERSION = "v0"


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
    client: TestClient,
    logged_user: dict[str, Any],
    expected: int,
):
    url = "/v0/storage/locations"
    assert url.startswith(PREFIX)

    resp = await client.get(url)
    data, error = await assert_status(resp, expected)

    if not error:
        assert "json_schema_extra" in FileLocation.model_config

        assert len(data) == len(FileLocation.model_json_schema()["examples"])
        assert data == FileLocation.model_json_schema()["examples"]


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_200_OK),
        (UserRole.USER, status.HTTP_200_OK),
        (UserRole.TESTER, status.HTTP_200_OK),
    ],
)
async def test_list_storage_paths(
    client: TestClient,
    logged_user: dict[str, Any],
    expected: int,
    location_id: LocationID,
):
    assert client.app
    url = client.app.router["list_storage_paths"].url_for(location_id=f"{location_id}")

    resp = await client.get(f"{url}")
    data, error = await assert_status(resp, expected)
    if not error:
        TypeAdapter(CursorPage[PathMetaDataGet]).validate_python(data)


_faker = Faker()


@pytest.fixture
def create_storage_paths_rpc_client_mock(
    mocker: MockerFixture,
) -> Callable[[str, Any], None]:
    def _(method: str, result_or_exception: Any):
        def side_effect(*args, **kwargs):
            if isinstance(result_or_exception, Exception):
                raise result_or_exception

            return result_or_exception

        for fct in (f"servicelib.rabbitmq.rpc_interfaces.storage.paths.{method}",):
            mocker.patch(fct, side_effect=side_effect)

    return _


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_202_ACCEPTED),
        (UserRole.USER, status.HTTP_202_ACCEPTED),
        (UserRole.TESTER, status.HTTP_202_ACCEPTED),
    ],
)
@pytest.mark.parametrize(
    "backend_result_or_exception",
    [
        AsyncJobGet(job_id=AsyncJobId(f"{_faker.uuid4()}")),
    ],
    ids=lambda x: type(x).__name__,
)
async def test_compute_path_size(
    client: TestClient,
    logged_user: dict[str, Any],
    expected: int,
    location_id: LocationID,
    faker: Faker,
    create_storage_paths_rpc_client_mock: Callable[[str, Any], None],
    backend_result_or_exception: Any,
):
    create_storage_paths_rpc_client_mock(
        submit_job.__name__,
        backend_result_or_exception,
    )

    assert client.app
    url = client.app.router["compute_path_size"].url_for(
        location_id=f"{location_id}",
        path=quote(faker.file_path(absolute=False), safe=""),
    )

    resp = await client.post(f"{url}")
    data, error = await assert_status(resp, expected)
    if not error:
        TypeAdapter(TaskGet).validate_python(data)


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
    client: TestClient,
    logged_user: dict[str, Any],
    expected: int,
):
    url = "/v0/storage/locations/0/datasets"
    assert url.startswith(PREFIX)
    assert client.app
    _url = client.app.router["list_datasets_metadata"].url_for(location_id="0")

    assert url == str(_url)

    resp = await client.get(url)
    data, error = await assert_status(resp, expected)

    if not error:
        assert "json_schema_extra" in DatasetMetaDataGet.model_config

        assert len(data) == len(DatasetMetaDataGet.model_json_schema()["examples"])
        assert data == DatasetMetaDataGet.model_json_schema()["examples"]


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_200_OK),
        (UserRole.USER, status.HTTP_200_OK),
        (UserRole.TESTER, status.HTTP_200_OK),
    ],
)
async def test_list_dataset_files_metadata(
    client: TestClient,
    logged_user: dict[str, Any],
    expected: int,
):
    url = "/v0/storage/locations/0/datasets/N:asdfsdf/metadata"
    assert url.startswith(PREFIX)
    assert client.app
    _url = client.app.router["list_dataset_files_metadata"].url_for(
        location_id="0", dataset_id="N:asdfsdf"
    )

    assert url == str(_url)

    resp = await client.get(url)
    data, error = await assert_status(resp, expected)

    if not error:
        assert "json_schema_extra" in FileMetaDataGet.model_config

        assert len(data) == len(FileMetaDataGet.model_json_schema()["examples"])
        assert data == [
            FileMetaDataGet.model_validate(e).model_dump(mode="json")
            for e in FileMetaDataGet.model_json_schema()["examples"]
        ]


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
    client: TestClient,
    logged_user: dict[str, Any],
    expected: int,
    faker: Faker,
):
    # tests redirect of path with quotes in path
    file_id = f"{faker.uuid4()}/{faker.uuid4()}/a/b/c/d/e/dat"
    quoted_file_id = quote(file_id, safe="")
    url = f"/v0/storage/locations/0/files/{quoted_file_id}/metadata"

    assert url.startswith(PREFIX)

    resp = await client.get(url)
    data, error = await assert_status(resp, expected)

    if not error:
        assert data
        model = FileMetaDataGet.model_validate(data)
        assert model


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
    client: TestClient,
    logged_user: dict[str, Any],
    expected: int,
):
    # tests composition of 2 queries
    file_id = "a/b/c/d/e/dat"
    url = "/v0/storage/locations/0/files/metadata?uuid_filter={}".format(
        quote(file_id, safe="")
    )

    assert url.startswith(PREFIX)

    resp = await client.get(url)
    data, error = await assert_status(resp, expected)

    if not error:
        assert len(data) == 2
        for item in data:
            model = FileMetaDataGet.model_validate(item)
            assert model


@pytest.fixture
def file_id(faker: Faker) -> StorageFileID:
    return TypeAdapter(StorageFileID).validate_python(
        f"{faker.uuid4()}/{faker.uuid4()}/{faker.file_name()} with spaces().dat"
    )


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_200_OK),
        (UserRole.USER, status.HTTP_200_OK),
        (UserRole.TESTER, status.HTTP_200_OK),
    ],
)
async def test_upload_file(
    client: TestClient,
    logged_user: dict[str, Any],
    expected: int,
    file_id: StorageFileID,
):
    url = f"/v0/storage/locations/0/files/{quote(file_id, safe='')}"

    assert url.startswith(PREFIX)

    resp = await client.put(url)
    data, error = await assert_status(resp, expected)
    if not error:
        assert not error
        assert data
        file_upload_schema = FileUploadSchema.model_validate(data)

        # let's abort
        resp = await client.post(f"{file_upload_schema.links.abort_upload.path}")
        data, error = await assert_status(resp, status.HTTP_204_NO_CONTENT)
        assert not error
        assert not data
