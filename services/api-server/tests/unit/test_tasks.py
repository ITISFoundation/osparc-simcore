# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from typing import Any

import pytest
from faker import Faker
from fastapi import status
from httpx import AsyncClient, BasicAuth
from models_library.api_schemas_long_running_tasks.tasks import TaskGet, TaskStatus
from models_library.api_schemas_rpc_async_jobs.exceptions import (
    BaseAsyncjobRpcError,
    JobAbortedError,
    JobError,
    JobNotDoneError,
    JobSchedulerError,
)
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.async_jobs_server import AsyncJobSideEffects
from simcore_service_api_server.models.schemas.base import ApiServerEnvelope

_faker = Faker()


@pytest.fixture
async def async_jobs_rpc_side_effects(
    async_job_error: BaseAsyncjobRpcError | None,
) -> Any:
    return AsyncJobSideEffects(exception=async_job_error)


@pytest.fixture
def mocked_async_jobs_rpc_api(
    mocker: MockerFixture,
    async_jobs_rpc_side_effects: Any,
    mocked_app_dependencies: None,
) -> dict[str, MockType]:
    """
    Mocks the catalog's simcore service RPC API for testing purposes.
    """
    from servicelib.rabbitmq.rpc_interfaces.async_jobs import async_jobs

    mocks = {}

    # Get all callable methods from the side effects class that are not built-ins
    side_effect_methods = [
        method_name
        for method_name in dir(async_jobs_rpc_side_effects)
        if not method_name.startswith("_")
        and callable(getattr(async_jobs_rpc_side_effects, method_name))
    ]

    # Create mocks for each method in catalog_rpc that has a corresponding side effect
    for method_name in side_effect_methods:
        assert hasattr(async_jobs, method_name)
        mocks[method_name] = mocker.patch.object(
            async_jobs,
            method_name,
            autospec=True,
            side_effect=getattr(async_jobs_rpc_side_effects, method_name),
        )

    return mocks


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
async def test_get_async_jobs(
    client: AsyncClient,
    mocked_async_jobs_rpc_api: dict[str, MockType],
    auth: BasicAuth,
    expected_status_code: int,
):

    response = await client.get("/v0/tasks", auth=auth)
    assert mocked_async_jobs_rpc_api["list_jobs"].called
    assert response.status_code == expected_status_code

    if response.status_code == status.HTTP_200_OK:
        result = ApiServerEnvelope[list[TaskGet]].model_validate_json(response.text)
        assert len(result.data) > 0
        assert all(isinstance(task, TaskGet) for task in result.data)
        task = result.data[0]
        assert task.abort_href == f"/v0/tasks/{task.task_id}:cancel"
        assert task.result_href == f"/v0/tasks/{task.task_id}/result"
        assert task.status_href == f"/v0/tasks/{task.task_id}"


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
    auth: BasicAuth,
    expected_status_code: int,
):
    task_id = f"{_faker.uuid4()}"
    response = await client.get(f"/v0/tasks/{task_id}/result", auth=auth)
    assert response.status_code == expected_status_code
    assert mocked_async_jobs_rpc_api["result"].called
    assert f"{mocked_async_jobs_rpc_api['result'].call_args[1]['job_id']}" == task_id
