# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

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
    ResultError,
    StatusError,
)
from models_library.api_schemas_storage.data_export_async_jobs import (
    AccessRightError,
    DataExportError,
    InvalidFileIdentifierError,
)
from models_library.api_schemas_webserver.storage import (
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
    submit_job,
)
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
    "backend_result_or_exception",
    [
        AsyncJobGet(job_id=AsyncJobId(f"{_faker.uuid4()}")),
        InvalidFileIdentifierError(file_id=Path("/my/file")),
        AccessRightError(user_id=_faker.pyint(min_value=0), file_id=Path("/my/file")),
        DataExportError(job_id=_faker.pyint(min_value=0)),
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
):
    create_storage_rpc_client_mock(
        submit_job.__name__,
        backend_result_or_exception,
    )

    _body = DataExportPost(
        paths=[f"{faker.uuid4()}/{faker.uuid4()}/{faker.file_name()}"]
    )
    response = await client.post(
        "/v0/storage/locations/0/export-data", data=_body.model_dump_json()
    )
    if isinstance(backend_result_or_exception, AsyncJobGet):
        assert response.status == status.HTTP_202_ACCEPTED
        Envelope[StorageAsyncJobGet].model_validate(await response.json())
    elif isinstance(backend_result_or_exception, InvalidFileIdentifierError):
        assert response.status == status.HTTP_404_NOT_FOUND
    elif isinstance(backend_result_or_exception, AccessRightError):
        assert response.status == status.HTTP_403_FORBIDDEN
    else:
        assert isinstance(backend_result_or_exception, DataExportError)
        assert response.status == status.HTTP_500_INTERNAL_SERVER_ERROR


@pytest.mark.parametrize("user_role", [UserRole.USER])
@pytest.mark.parametrize(
    "backend_result_or_exception",
    [
        AsyncJobStatus(
            job_id=f"{_faker.uuid4()}",
            progress=ProgressReport(actual_value=0.5, total=1.0),
            done=False,
            started=datetime.now(),
            stopped=None,
        ),
        StatusError(job_id=_faker.uuid4()),
    ],
    ids=lambda x: type(x).__name__,
)
async def test_get_async_jobs_status(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    create_storage_rpc_client_mock: Callable[[str, Any], None],
    backend_result_or_exception: Any,
):
    _job_id = AsyncJobId(_faker.uuid4())
    create_storage_rpc_client_mock(get_status.__name__, backend_result_or_exception)

    response = await client.get(f"/v0/storage/async-jobs/{_job_id}/status")
    if isinstance(backend_result_or_exception, AsyncJobStatus):
        assert response.status == status.HTTP_200_OK
        response_body_data = (
            Envelope[StorageAsyncJobGet].model_validate(await response.json()).data
        )
        assert response_body_data is not None
    elif isinstance(backend_result_or_exception, StatusError):
        assert response.status == status.HTTP_500_INTERNAL_SERVER_ERROR
    else:
        pytest.fail("Incorrectly configured test")


@pytest.mark.parametrize("user_role", [UserRole.USER])
@pytest.mark.parametrize("abort_success", [True, False])
async def test_abort_async_jobs(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    create_storage_rpc_client_mock: Callable[[str, Any], None],
    faker: Faker,
    abort_success: bool,
):
    _job_id = AsyncJobId(faker.uuid4())
    create_storage_rpc_client_mock(
        abort.__name__, AsyncJobAbort(result=abort_success, job_id=_job_id)
    )

    response = await client.post(f"/v0/storage/async-jobs/{_job_id}:abort")

    if abort_success:
        assert response.status == status.HTTP_200_OK
    else:
        assert response.status == status.HTTP_500_INTERNAL_SERVER_ERROR


@pytest.mark.parametrize("user_role", [UserRole.USER])
@pytest.mark.parametrize(
    "backend_result_or_exception",
    [
        AsyncJobResult(result=None, error=_faker.text()),
        ResultError(job_id=_faker.uuid4()),
    ],
    ids=lambda x: type(x).__name__,
)
async def test_get_async_job_result(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    create_storage_rpc_client_mock: Callable[[str, Any], None],
    faker: Faker,
    backend_result_or_exception: Any,
):
    _job_id = AsyncJobId(faker.uuid4())
    create_storage_rpc_client_mock(get_result.__name__, backend_result_or_exception)

    response = await client.get(f"/v0/storage/async-jobs/{_job_id}/result")

    if isinstance(backend_result_or_exception, AsyncJobResult):
        assert response.status == status.HTTP_200_OK
    elif isinstance(backend_result_or_exception, ResultError):
        assert response.status == status.HTTP_500_INTERNAL_SERVER_ERROR
    else:
        pytest.fail("Incorrectly configured test")


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_get_user_async_jobs(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    create_storage_rpc_client_mock: Callable[[str, Any], None],
):
    create_storage_rpc_client_mock(
        list_jobs.__name__, [StorageAsyncJobGet(job_id=AsyncJobId(_faker.uuid4()))]
    )

    response = await client.get("/v0/storage/async-jobs")

    assert response.status == status.HTTP_200_OK
    Envelope[list[StorageAsyncJobGet]].model_validate(await response.json())
