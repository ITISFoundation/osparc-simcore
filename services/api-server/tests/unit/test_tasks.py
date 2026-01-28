# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


from typing import Literal

import pytest
from celery.exceptions import CeleryError  # pylint: disable=no-name-in-module
from faker import Faker
from fastapi import status
from httpx import AsyncClient, BasicAuth
from models_library.api_schemas_long_running_tasks.tasks import TaskGet, TaskStatus
from models_library.progress_bar import ProgressReport, ProgressStructuredMessage
from models_library.utils.json_schema import GenerateResolvedJsonSchema
from pytest_mock import MockerFixture, MockType
from servicelib.celery.models import TaskState, TaskUUID
from servicelib.celery.models import TaskStatus as CeleryTaskStatus
from simcore_service_api_server.api.routes import tasks as task_routes
from simcore_service_api_server.models.schemas.base import ApiServerEnvelope

pytest_simcore_core_services_selection = ["postgres", "rabbit"]
pytest_plugins = [
    "pytest_simcore.celery_library_mocks",
]

_faker = Faker()


@pytest.fixture
def mock_task_manager(mocker: MockerFixture, mock_task_manager_object: MockType) -> MockType:
    def _get_task_manager(app):
        return mock_task_manager_object

    mocker.patch.object(task_routes, "get_task_manager", _get_task_manager)
    return mock_task_manager_object


async def test_list_celery_tasks(
    mock_task_manager: MockType,
    client: AsyncClient,
    auth: BasicAuth,
):
    response = await client.get("/v0/tasks", auth=auth)
    assert mock_task_manager.list_tasks.called
    assert response.status_code == status.HTTP_200_OK

    result = ApiServerEnvelope[list[TaskGet]].model_validate_json(response.text)
    assert len(result.data) > 0
    assert all(isinstance(task, TaskGet) for task in result.data)
    task = result.data[0]
    assert task.abort_href == f"/v0/tasks/{task.task_id}:cancel"
    assert task.result_href == f"/v0/tasks/{task.task_id}/result"
    assert task.status_href == f"/v0/tasks/{task.task_id}"


async def test_get_task_status(
    mock_task_manager: MockType,
    client: AsyncClient,
    auth: BasicAuth,
):
    task_id = f"{_faker.uuid4()}"
    response = await client.get(f"/v0/tasks/{task_id}", auth=auth)
    assert mock_task_manager.get_task_status.called
    assert response.status_code == status.HTTP_200_OK
    TaskStatus.model_validate_json(response.text)


async def test_cancel_task(
    mock_task_manager: MockType,
    client: AsyncClient,
    auth: BasicAuth,
):
    task_id = f"{_faker.uuid4()}"
    response = await client.post(f"/v0/tasks/{task_id}:cancel", auth=auth)
    assert mock_task_manager.cancel_task.called
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_get_task_result(
    mock_task_manager: MockType,
    client: AsyncClient,
    auth: BasicAuth,
):
    task_id = f"{_faker.uuid4()}"
    response = await client.get(f"/v0/tasks/{task_id}/result", auth=auth)
    assert response.status_code == status.HTTP_200_OK
    assert mock_task_manager.get_task_result.called
    assert f"{mock_task_manager.get_task_result.call_args[1]['task_uuid']}" == task_id


@pytest.mark.parametrize(
    "method, url, list_tasks_return_value, get_task_status_return_value, cancel_task_return_value, get_task_result_return_value, expected_status_code",
    [
        (
            "GET",
            "/v0/tasks",
            CeleryError(),
            None,
            None,
            None,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ),
        (
            "GET",
            f"/v0/tasks/{_faker.uuid4()}",
            None,
            CeleryError(),
            None,
            None,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ),
        (
            "POST",
            f"/v0/tasks/{_faker.uuid4()}:cancel",
            None,
            None,
            CeleryError(),
            None,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ),
        (
            "GET",
            f"/v0/tasks/{_faker.uuid4()}/result",
            None,
            CeleryError(),
            None,
            None,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ),
        (
            "GET",
            f"/v0/tasks/{_faker.uuid4()}/result",
            None,
            CeleryTaskStatus(
                task_uuid=TaskUUID("123e4567-e89b-12d3-a456-426614174000"),
                task_state=TaskState.STARTED,
                progress_report=ProgressReport(
                    actual_value=0.5,
                    total=1.0,
                    unit="Byte",
                    message=ProgressStructuredMessage.model_validate(
                        ProgressStructuredMessage.model_json_schema(schema_generator=GenerateResolvedJsonSchema)[
                            "examples"
                        ][0]
                    ),
                ),
            ),
            None,
            None,
            status.HTTP_404_NOT_FOUND,
        ),
    ],
)
async def test_celery_error_propagation(
    mock_task_manager: MockType,
    client: AsyncClient,
    auth: BasicAuth,
    method: Literal["GET", "POST"],
    url: str,
    expected_status_code: int,
):
    response = await client.request(method=method, url=url, auth=auth)
    assert response.status_code == expected_status_code
