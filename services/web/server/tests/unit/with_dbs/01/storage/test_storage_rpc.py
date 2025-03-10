from collections.abc import Callable

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
from pathlib import Path
from typing import Any

import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
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
    JobNotDoneError,
    JobSchedulerError,
)
from models_library.api_schemas_storage.data_export_async_jobs import (
    AccessRightError,
    InvalidFileIdentifierError,
)
from models_library.api_schemas_webserver.storage import (
    AsyncJobLinks,
    DataExportPost,
    StorageAsyncJobGet,
)
from models_library.generics import Envelope
from models_library.progress_bar import ProgressReport
from pytest_mock import MockerFixture
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from servicelib.rabbitmq.rpc_interfaces.async_jobs.async_jobs import (
    abort,
    get_result,
    get_status,
    list_jobs,
)
from servicelib.rabbitmq.rpc_interfaces.storage.data_export import start_data_export
from simcore_postgres_database.models.users import UserRole

_faker = Faker()


@pytest.fixture
def create_storage_rpc_client_mock(mocker: MockerFixture) -> Callable[[str, Any], None]:
    def _(method: str, result_or_exception: Any):
        def side_effect(*args, **kwargs):
            if isinstance(result_or_exception, Exception):
                raise result_or_exception

            return result_or_exception

        mocker.patch(
            f"simcore_service_webserver.storage._rest.{method}",
            side_effect=side_effect,
        )

    return _


@pytest.mark.parametrize("user_role", [UserRole.USER])
@pytest.mark.parametrize(
    "backend_result_or_exception, expected_status",
    [
        (AsyncJobGet(job_id=AsyncJobId(f"{_faker.uuid4()}")), status.HTTP_202_ACCEPTED),
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
        (JobSchedulerError(exc=_faker.text()), status.HTTP_500_INTERNAL_SERVER_ERROR),
    ],
    ids=lambda x: type(x).__name__,
)
async def test_data_export(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    create_storage_rpc_client_mock: Callable[[str, Any], None],
    faker: Faker,
    backend_result_or_exception: Any,
    expected_status: int,
):
    create_storage_rpc_client_mock(
        start_data_export.__name__,
        backend_result_or_exception,
    )

    _body = DataExportPost(
        paths=[f"{faker.uuid4()}/{faker.uuid4()}/{faker.file_name()}"]
    )
    response = await client.post(
        "/v0/storage/locations/0/export-data", data=_body.model_dump_json()
    )
    assert response.status == expected_status
    if response.status == status.HTTP_202_ACCEPTED:
        Envelope[StorageAsyncJobGet].model_validate(await response.json())


@pytest.mark.parametrize("user_role", [UserRole.USER])
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
    ],
    ids=lambda x: type(x).__name__,
)
async def test_get_async_jobs_status(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    create_storage_rpc_client_mock: Callable[[str, Any], None],
    backend_result_or_exception: Any,
    expected_status: int,
):
    _job_id = AsyncJobId(_faker.uuid4())
    create_storage_rpc_client_mock(get_status.__name__, backend_result_or_exception)

    response = await client.get(f"/v0/storage/async-jobs/{_job_id}/status")
    assert response.status == expected_status
    if response.status == status.HTTP_200_OK:
        response_body_data = (
            Envelope[StorageAsyncJobGet].model_validate(await response.json()).data
        )
        assert response_body_data is not None


@pytest.mark.parametrize("user_role", [UserRole.USER])
@pytest.mark.parametrize(
    "backend_result_or_exception, expected_status",
    [
        (
            AsyncJobAbort(result=True, job_id=AsyncJobId(_faker.uuid4())),
            status.HTTP_200_OK,
        ),
        (JobSchedulerError(exc=_faker.text()), status.HTTP_500_INTERNAL_SERVER_ERROR),
    ],
    ids=lambda x: type(x).__name__,
)
async def test_abort_async_jobs(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    create_storage_rpc_client_mock: Callable[[str, Any], None],
    faker: Faker,
    backend_result_or_exception: Any,
    expected_status: int,
):
    _job_id = AsyncJobId(faker.uuid4())
    create_storage_rpc_client_mock(abort.__name__, backend_result_or_exception)

    response = await client.post(f"/v0/storage/async-jobs/{_job_id}:abort")
    assert response.status == expected_status


@pytest.mark.parametrize("user_role", [UserRole.USER])
@pytest.mark.parametrize(
    "result_or_exception, expected_status",
    [
        (JobNotDoneError(job_id=_faker.uuid4()), status.HTTP_409_CONFLICT),
        (AsyncJobResult(result=None), status.HTTP_200_OK),
        (JobError(job_id=_faker.uuid4()), status.HTTP_500_INTERNAL_SERVER_ERROR),
        (JobAbortedError(job_id=_faker.uuid4()), status.HTTP_410_GONE),
        (JobSchedulerError(exc=_faker.text()), status.HTTP_500_INTERNAL_SERVER_ERROR),
    ],
    ids=lambda x: type(x).__name__,
)
async def test_get_async_job_result(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    create_storage_rpc_client_mock: Callable[[str, Any], None],
    faker: Faker,
    result_or_exception: Any,
    expected_status: int,
):
    _job_id = AsyncJobId(faker.uuid4())
    create_storage_rpc_client_mock(get_result.__name__, result_or_exception)

    response = await client.get(f"/v0/storage/async-jobs/{_job_id}/result")
    assert response.status == expected_status


@pytest.mark.parametrize("user_role", [UserRole.USER])
@pytest.mark.parametrize(
    "backend_result_or_exception, expected_status",
    [
        (
            [
                StorageAsyncJobGet(
                    job_id=AsyncJobId(_faker.uuid4()),
                    links=AsyncJobLinks(
                        status_href=_faker.uri(),
                        abort_href=_faker.uri(),
                        result_href=_faker.uri(),
                    ),
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
    create_storage_rpc_client_mock: Callable[[str, Any], None],
    backend_result_or_exception: Any,
    expected_status: int,
):
    create_storage_rpc_client_mock(list_jobs.__name__, backend_result_or_exception)

    response = await client.get("/v0/storage/async-jobs")
    assert response.status == expected_status
    if response.status == status.HTTP_200_OK:
        Envelope[list[StorageAsyncJobGet]].model_validate(await response.json())
