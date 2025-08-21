# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


from collections.abc import Callable
from typing import Literal

import pytest
from celery.exceptions import CeleryError
from faker import Faker
from fastapi import status
from httpx import AsyncClient, BasicAuth
from models_library.api_schemas_long_running_tasks.tasks import TaskGet, TaskStatus
from models_library.api_schemas_rpc_async_jobs.exceptions import (
    JobAbortedError,
    JobError,
    JobNotDoneError,
    JobSchedulerError,
)
from pytest_mock import MockerFixture, MockType, mocker
from simcore_service_api_server.api.routes import tasks as task_routes
from simcore_service_api_server.models.schemas.base import ApiServerEnvelope

pytest_simcore_core_services_selection = ["postgres", "rabbit"]
pytest_plugins = [
    "pytest_simcore.celery_library_mocks",
]

_faker = Faker()


@pytest.fixture
def mock_task_manager(
    mocker: MockerFixture, mock_task_manager_object: MockType
) -> MockType:

    def _get_task_manager(app):
        return mock_task_manager_object

    mocker.patch.object(task_routes, "get_task_manager", _get_task_manager)
    return mock_task_manager_object


@pytest.fixture
def mock_task_manager_raising_factory(
    mocker: MockerFixture,
    mock_task_manager_object_raising_factory: Callable[[Exception], MockType],
) -> Callable[[Exception], MockType]:

    def _(task_manager_exception: Exception):
        mock = mock_task_manager_object_raising_factory(task_manager_exception)

        def _get_task_manager(app):
            return mock

        mocker.patch.object(task_routes, "get_task_manager", _get_task_manager)
        return mock

    return _


async def test_list_celery_tasks(
    mock_task_manager: MockType,
    client: AsyncClient,
    auth: BasicAuth,
):

    response = await client.get("/v0/tasks", auth=auth)
    assert response.status_code == status.HTTP_200_OK

    result = ApiServerEnvelope[list[TaskGet]].model_validate_json(response.text)
    assert len(result.data) > 0
    assert all(isinstance(task, TaskGet) for task in result.data)
    task = result.data[0]
    assert task.abort_href == f"/v0/tasks/{task.task_id}:cancel"
    assert task.result_href == f"/v0/tasks/{task.task_id}/result"
    assert task.status_href == f"/v0/tasks/{task.task_id}"


@pytest.mark.parametrize(
    "method, url, celery_exception, expected_status_code",
    [
        ("GET", "/v0/tasks", CeleryError(), status.HTTP_500_INTERNAL_SERVER_ERROR),
        (
            "GET",
            f"/v0/tasks/{_faker.uuid4()}",
            CeleryError(),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ),
        (
            "POST",
            f"/v0/tasks/{_faker.uuid4()}:cancel",
            CeleryError(),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ),
        (
            "GET",
            f"/v0/tasks/{_faker.uuid4()}/result",
            CeleryError(),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ),
    ],
)
async def test_celery_tasks_error_propagation(
    mock_task_manager_raising_factory: Callable[[Exception], None],
    client: AsyncClient,
    auth: BasicAuth,
    method: Literal["GET", "POST"],
    url: str,
    celery_exception: Exception,
    expected_status_code: int,
):
    mock_task_manager_raising_factory(celery_exception)

    response = await client.request(method=method, url=url, auth=auth)
    assert response.status_code == expected_status_code


@pytest.mark.parametrize(
    "async_job_error, expected_status_code",
    [
        (None, status.HTTP_200_OK),
        (
            JobSchedulerError(
                exc=Exception("A very rare exception raised by the scheduler")
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ),
    ],
)
async def test_get_async_jobs_status(
    client: AsyncClient,
    mocked_async_jobs_rpc_api: dict[str, MockType],
    async_job_error: Exception | None,
    auth: BasicAuth,
    expected_status_code: int,
):
    task_id = f"{_faker.uuid4()}"
    response = await client.get(f"/v0/tasks/{task_id}", auth=auth)
    assert mocked_async_jobs_rpc_api["status"].called
    assert f"{mocked_async_jobs_rpc_api['status'].call_args[1]['job_id']}" == task_id
    assert response.status_code == expected_status_code
    if response.status_code == status.HTTP_200_OK:
        TaskStatus.model_validate_json(response.text)


@pytest.mark.parametrize(
    "async_job_error, expected_status_code",
    [
        (None, status.HTTP_204_NO_CONTENT),
        (
            JobSchedulerError(
                exc=Exception("A very rare exception raised by the scheduler")
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ),
    ],
)
async def test_cancel_async_job(
    client: AsyncClient,
    mocked_async_jobs_rpc_api: dict[str, MockType],
    async_job_error: Exception | None,
    auth: BasicAuth,
    expected_status_code: int,
):
    task_id = f"{_faker.uuid4()}"
    response = await client.post(f"/v0/tasks/{task_id}:cancel", auth=auth)
    assert mocked_async_jobs_rpc_api["cancel"].called
    assert f"{mocked_async_jobs_rpc_api['cancel'].call_args[1]['job_id']}" == task_id
    assert response.status_code == expected_status_code


@pytest.mark.parametrize(
    "async_job_error, expected_status_code",
    [
        (None, status.HTTP_200_OK),
        (
            JobError(
                job_id=_faker.uuid4(),
                exc_type=Exception,
                exc_message="An exception from inside the async job",
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ),
        (
            JobNotDoneError(job_id=_faker.uuid4()),
            status.HTTP_404_NOT_FOUND,
        ),
        (
            JobAbortedError(job_id=_faker.uuid4()),
            status.HTTP_409_CONFLICT,
        ),
        (
            JobSchedulerError(
                exc=Exception("A very rare exception raised by the scheduler")
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ),
    ],
)
async def test_get_async_job_result(
    client: AsyncClient,
    mocked_async_jobs_rpc_api: dict[str, MockType],
    async_job_error: Exception | None,
    auth: BasicAuth,
    expected_status_code: int,
):
    task_id = f"{_faker.uuid4()}"
    response = await client.get(f"/v0/tasks/{task_id}/result", auth=auth)
    assert response.status_code == expected_status_code
    assert mocked_async_jobs_rpc_api["result"].called
    assert f"{mocked_async_jobs_rpc_api['result'].call_args[1]['job_id']}" == task_id
