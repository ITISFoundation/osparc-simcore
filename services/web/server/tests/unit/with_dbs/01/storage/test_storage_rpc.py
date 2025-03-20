# pylint: disable=too-many-arguments
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
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
from models_library.api_schemas_storage.data_export_async_jobs import (
    AccessRightError,
    InvalidFileIdentifierError,
)
from models_library.api_schemas_webserver._base import OutputSchema
from models_library.api_schemas_webserver.storage import (
    DataExportPost,
)
from models_library.generics import Envelope
from models_library.progress_bar import ProgressReport
from pytest_mock import MockerFixture
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from servicelib.rabbitmq.rpc_interfaces.async_jobs import async_jobs
from servicelib.rabbitmq.rpc_interfaces.storage.data_export import start_data_export
from simcore_postgres_database.models.users import UserRole
from yarl import URL

_faker = Faker()
_user_roles: Final[list[UserRole]] = [
    UserRole.GUEST,
    UserRole.USER,
    UserRole.TESTER,
    UserRole.PRODUCT_OWNER,
    UserRole.ADMIN,
]


API_VERSION: Final[str] = "v0"


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
    create_storage_rpc_client_mock: Callable[[str, str, Any], None],
    faker: Faker,
    backend_result_or_exception: Any,
    expected_status: int,
):
    create_storage_rpc_client_mock(
        "simcore_service_webserver.storage._rest",
        start_data_export.__name__,
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
async def test_abort_async_jobs(
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
        start_data_export.__name__,
        AsyncJobGet(job_id=AsyncJobId(f"{_faker.uuid4()}")),
    )

    _body = DataExportPost(
        paths=[f"{faker.uuid4()}/{faker.uuid4()}/{faker.file_name()}"]
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
