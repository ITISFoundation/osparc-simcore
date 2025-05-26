# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import Callable
from pathlib import Path
from typing import Any, Final
from urllib.parse import quote

import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
from fastapi_pagination.cursor import CursorPage
from models_library.api_schemas_long_running_tasks.tasks import (
    TaskGet,
    TaskResult,
    TaskStatus,
)
from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobAbort,
    AsyncJobGet,
    AsyncJobId,
    AsyncJobResult,
    AsyncJobStatus,
)
from models_library.api_schemas_rpc_async_jobs.exceptions import (
    JobAbortedError,
    JobError,
    JobMissingError,
    JobNotDoneError,
    JobSchedulerError,
)
from models_library.api_schemas_storage.export_data_async_jobs import (
    AccessRightError,
    InvalidFileIdentifierError,
)
from models_library.api_schemas_storage.storage_schemas import (
    DatasetMetaDataGet,
    FileLocation,
    FileMetaDataGet,
    FileUploadSchema,
    PathMetaDataGet,
)
from models_library.api_schemas_webserver._base import OutputSchema
from models_library.api_schemas_webserver.storage import (
    BatchDeletePathsBodyParams,
    DataExportPost,
    PathToExport,
)
from models_library.generics import Envelope
from models_library.progress_bar import ProgressReport
from models_library.projects_nodes_io import LocationID, StorageFileID
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from servicelib.rabbitmq.rpc_interfaces.async_jobs import async_jobs
from servicelib.rabbitmq.rpc_interfaces.async_jobs.async_jobs import (
    submit,
)
from servicelib.rabbitmq.rpc_interfaces.storage.simcore_s3 import start_export_data
from simcore_postgres_database.models.users import UserRole
from yarl import URL

API_VERSION = "v0"


PREFIX = "/" + API_VERSION + "/storage"

_faker = Faker()
_user_roles: Final[list[UserRole]] = [
    UserRole.GUEST,
    UserRole.USER,
    UserRole.TESTER,
    UserRole.PRODUCT_OWNER,
    UserRole.ADMIN,
]


@pytest.mark.xfail(
    reason="This is really weird: A first test that fails is necessary to make this test module work with pytest-asyncio>=0.24.0. "
    "Maybe because of module/session event loops?"
)
async def test_pytest_asyncio_failure(
    client: TestClient,
):
    url = "/v0/storage/locations"
    assert url.startswith(PREFIX)
    await client.get(url)


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
        AsyncJobGet(
            job_id=AsyncJobId(f"{_faker.uuid4()}"), job_name="compute_path_size"
        ),
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
        submit.__name__,
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
        (UserRole.GUEST, status.HTTP_202_ACCEPTED),
        (UserRole.USER, status.HTTP_202_ACCEPTED),
        (UserRole.TESTER, status.HTTP_202_ACCEPTED),
    ],
)
@pytest.mark.parametrize(
    "backend_result_or_exception",
    [
        AsyncJobGet(
            job_id=AsyncJobId(f"{_faker.uuid4()}"), job_name="batch_delete_paths"
        ),
    ],
    ids=lambda x: type(x).__name__,
)
async def test_batch_delete_paths(
    client: TestClient,
    logged_user: dict[str, Any],
    expected: int,
    location_id: LocationID,
    faker: Faker,
    create_storage_paths_rpc_client_mock: Callable[[str, Any], None],
    backend_result_or_exception: Any,
):
    create_storage_paths_rpc_client_mock(
        submit.__name__,
        backend_result_or_exception,
    )

    body = BatchDeletePathsBodyParams(
        paths={Path(f"{faker.file_path(absolute=False)}")}
    )

    assert client.app
    url = client.app.router["batch_delete_paths"].url_for(
        location_id=f"{location_id}",
    )

    resp = await client.post(f"{url}", json=body.model_dump(mode="json"))
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


@pytest.fixture
def create_storage_rpc_client_mock(
    mocker: MockerFixture,
) -> Callable[[str, str, Any], None]:
    def _(module: str, method: str, result_or_exception: Any):
        def side_effect(*args, **kwargs):
            if isinstance(result_or_exception, Exception):
                raise result_or_exception

            return result_or_exception

        for fct in (f"{module}.{method}",):
            mocker.patch(fct, side_effect=side_effect)

    return _


@pytest.mark.parametrize("user_role", _user_roles)
@pytest.mark.parametrize(
    "backend_result_or_exception, expected_status",
    [
        (
            (
                AsyncJobGet(
                    job_id=AsyncJobId(f"{_faker.uuid4()}"), job_name="export_data"
                ),
                None,
            ),
            status.HTTP_202_ACCEPTED,
        ),
        (
            InvalidFileIdentifierError(file_id=Path("/my/file")),
            status.HTTP_404_NOT_FOUND,
        ),
        (
            AccessRightError(
                user_id=_faker.pyint(min_value=0), file_id=Path("/my/file")
            ),
            status.HTTP_403_FORBIDDEN,
        ),
        (
            JobSchedulerError(exc=_faker.text()),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ),
    ],
    ids=lambda x: type(x).__name__,
)
async def test_export_data(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    create_storage_rpc_client_mock: Callable[[str, str, Any], None],
    faker: Faker,
    backend_result_or_exception: Any,
    expected_status: int,
):
    create_storage_rpc_client_mock(
        "simcore_service_webserver.storage._rest",
        start_export_data.__name__,
        backend_result_or_exception,
    )

    _body = DataExportPost(
        paths=[f"{faker.uuid4()}/{faker.uuid4()}/{faker.file_name()}"]
    )
    response = await client.post(
        f"/{API_VERSION}/storage/locations/0/export-data", data=_body.model_dump_json()
    )
    assert response.status == expected_status
    if response.status == status.HTTP_202_ACCEPTED:
        Envelope[TaskGet].model_validate(await response.json())


@pytest.mark.parametrize("user_role", _user_roles)
@pytest.mark.parametrize(
    "backend_result_or_exception, expected_status",
    [
        (
            AsyncJobStatus(
                job_id=AsyncJobId(f"{_faker.uuid4()}"),
                progress=ProgressReport(actual_value=0.5, total=1.0),
                done=False,
            ),
            status.HTTP_200_OK,
        ),
        (JobSchedulerError(exc=_faker.text()), status.HTTP_500_INTERNAL_SERVER_ERROR),
        (JobMissingError(job_id=_faker.uuid4()), status.HTTP_404_NOT_FOUND),
    ],
    ids=lambda x: type(x).__name__,
)
async def test_get_async_jobs_status(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    create_storage_rpc_client_mock: Callable[[str, str, Any], None],
    backend_result_or_exception: Any,
    expected_status: int,
):
    _job_id = AsyncJobId(_faker.uuid4())
    create_storage_rpc_client_mock(
        "simcore_service_webserver.tasks._rest",
        f"async_jobs.{async_jobs.status.__name__}",
        backend_result_or_exception,
    )

    response = await client.get(f"/{API_VERSION}/tasks/{_job_id}")
    assert response.status == expected_status
    if response.status == status.HTTP_200_OK:
        response_body_data = (
            Envelope[TaskStatus].model_validate(await response.json()).data
        )
        assert response_body_data is not None


@pytest.mark.parametrize("user_role", _user_roles)
@pytest.mark.parametrize(
    "backend_result_or_exception, expected_status",
    [
        (
            AsyncJobAbort(result=True, job_id=AsyncJobId(_faker.uuid4())),
            status.HTTP_204_NO_CONTENT,
        ),
        (JobSchedulerError(exc=_faker.text()), status.HTTP_500_INTERNAL_SERVER_ERROR),
        (JobMissingError(job_id=_faker.uuid4()), status.HTTP_404_NOT_FOUND),
    ],
    ids=lambda x: type(x).__name__,
)
async def test_cancel_async_jobs(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    create_storage_rpc_client_mock: Callable[[str, str, Any], None],
    faker: Faker,
    backend_result_or_exception: Any,
    expected_status: int,
):
    _job_id = AsyncJobId(faker.uuid4())
    create_storage_rpc_client_mock(
        "simcore_service_webserver.tasks._rest",
        f"async_jobs.{async_jobs.cancel.__name__}",
        backend_result_or_exception,
    )

    response = await client.delete(f"/{API_VERSION}/tasks/{_job_id}")
    assert response.status == expected_status


@pytest.mark.parametrize("user_role", _user_roles)
@pytest.mark.parametrize(
    "backend_result_or_exception, expected_status",
    [
        (JobNotDoneError(job_id=_faker.uuid4()), status.HTTP_404_NOT_FOUND),
        (AsyncJobResult(result=None), status.HTTP_200_OK),
        (JobError(job_id=_faker.uuid4()), status.HTTP_500_INTERNAL_SERVER_ERROR),
        (JobAbortedError(job_id=_faker.uuid4()), status.HTTP_410_GONE),
        (JobSchedulerError(exc=_faker.text()), status.HTTP_500_INTERNAL_SERVER_ERROR),
        (JobMissingError(job_id=_faker.uuid4()), status.HTTP_404_NOT_FOUND),
    ],
    ids=lambda x: type(x).__name__,
)
async def test_get_async_job_result(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    create_storage_rpc_client_mock: Callable[[str, str, Any], None],
    faker: Faker,
    backend_result_or_exception: Any,
    expected_status: int,
):
    _job_id = AsyncJobId(faker.uuid4())
    create_storage_rpc_client_mock(
        "simcore_service_webserver.tasks._rest",
        f"async_jobs.{async_jobs.result.__name__}",
        backend_result_or_exception,
    )

    response = await client.get(f"/{API_VERSION}/tasks/{_job_id}/result")
    assert response.status == expected_status


@pytest.mark.parametrize("user_role", _user_roles)
@pytest.mark.parametrize(
    "backend_result_or_exception, expected_status",
    [
        (
            [
                AsyncJobGet(
                    job_id=AsyncJobId(_faker.uuid4()),
                    job_name="task_name",
                )
            ],
            status.HTTP_200_OK,
        ),
        (JobSchedulerError(exc=_faker.text()), status.HTTP_500_INTERNAL_SERVER_ERROR),
    ],
    ids=lambda x: type(x).__name__,
)
async def test_get_user_async_jobs(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    create_storage_rpc_client_mock: Callable[[str, str, Any], None],
    backend_result_or_exception: Any,
    expected_status: int,
):
    create_storage_rpc_client_mock(
        "simcore_service_webserver.tasks._rest",
        f"async_jobs.{async_jobs.list_jobs.__name__}",
        backend_result_or_exception,
    )

    response = await client.get(f"/{API_VERSION}/tasks")
    assert response.status == expected_status
    if response.status == status.HTTP_200_OK:
        Envelope[list[TaskGet]].model_validate(await response.json())


@pytest.mark.parametrize("user_role", _user_roles)
@pytest.mark.parametrize(
    "http_method, href, backend_method, backend_object, return_status, return_schema",
    [
        (
            "GET",
            "status_href",
            async_jobs.status.__name__,
            AsyncJobStatus(
                job_id=AsyncJobId(_faker.uuid4()),
                progress=ProgressReport(actual_value=0.5, total=1.0),
                done=False,
            ),
            status.HTTP_200_OK,
            TaskStatus,
        ),
        (
            "DELETE",
            "abort_href",
            async_jobs.cancel.__name__,
            AsyncJobAbort(result=True, job_id=AsyncJobId(_faker.uuid4())),
            status.HTTP_204_NO_CONTENT,
            None,
        ),
        (
            "GET",
            "result_href",
            async_jobs.result.__name__,
            AsyncJobResult(result=None),
            status.HTTP_200_OK,
            TaskResult,
        ),
    ],
)
async def test_get_async_job_links(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    create_storage_rpc_client_mock: Callable[[str, str, Any], None],
    faker: Faker,
    http_method: str,
    href: str,
    backend_method: str,
    backend_object: Any,
    return_status: int,
    return_schema: OutputSchema | None,
):
    create_storage_rpc_client_mock(
        "simcore_service_webserver.storage._rest",
        start_export_data.__name__,
        (
            AsyncJobGet(
                job_id=AsyncJobId(f"{_faker.uuid4()}"),
                job_name="export_data",
            ),
            None,
        ),
    )

    _body = DataExportPost(
        paths=[PathToExport(f"{faker.uuid4()}/{faker.uuid4()}/{faker.file_name()}")]
    )
    response = await client.post(
        f"/{API_VERSION}/storage/locations/0/export-data", data=_body.model_dump_json()
    )
    assert response.status == status.HTTP_202_ACCEPTED
    response_body_data = Envelope[TaskGet].model_validate(await response.json()).data
    assert response_body_data is not None

    # Call the different links and check the correct model and return status
    create_storage_rpc_client_mock(
        "simcore_service_webserver.tasks._rest",
        f"async_jobs.{backend_method}",
        backend_object,
    )
    response = await client.request(
        http_method, URL(getattr(response_body_data, href)).path
    )
    assert response.status == return_status
    if return_schema:
        Envelope[return_schema].model_validate(await response.json())
