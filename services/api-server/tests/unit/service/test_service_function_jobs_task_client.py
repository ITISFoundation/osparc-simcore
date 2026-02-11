# pylint: disable=redefined-outer-name

import json
from collections.abc import Callable

import pytest
from celery_library.errors import TaskNotFoundError
from faker import Faker
from models_library.products import ProductName
from models_library.progress_bar import ProgressReport
from models_library.users import UserID
from pydantic import TypeAdapter
from pytest_mock import MockerFixture, MockType
from servicelib.celery.models import TaskState, TaskStatus, TaskUUID
from servicelib.celery.task_manager import TaskManager
from simcore_service_api_server._service_function_jobs_task_client import (
    _celery_task_status,
)
from simcore_service_api_server.models.schemas.functions import (
    FunctionJobCreationTaskStatus,
)

_faker = Faker()


@pytest.fixture
async def create_mock_task_manager(
    mocker: MockerFixture,
) -> Callable[[TaskStatus | Exception], MockType]:
    def _(status_or_exception: TaskStatus | Exception) -> MockType:
        mock_task_manager = mocker.Mock(spec=TaskManager)
        if isinstance(status_or_exception, Exception):

            async def _raise(*args, **kwargs):
                raise status_or_exception

            mock_task_manager.get_task_status.side_effect = _raise
        else:
            mock_task_manager.get_task_status.return_value = status_or_exception
        return mock_task_manager

    return _


@pytest.mark.parametrize(
    "status_or_exception",
    [
        TaskStatus(
            task_uuid=TypeAdapter(TaskUUID).validate_python(_faker.uuid4()),
            task_state=state,
            progress_report=ProgressReport(actual_value=3.14),
        )
        for state in list(TaskState)
    ]
    + [TaskNotFoundError(task_uuid=_faker.uuid4(), owner_metadata=json.dumps({"owner": "test-owner"}))],
)
@pytest.mark.parametrize("job_creation_task_id", [_faker.uuid4(), None])
async def test_celery_status_conversion(
    status_or_exception: TaskStatus | Exception,
    job_creation_task_id: str | None,
    create_mock_task_manager: Callable[[TaskStatus | Exception], MockType],
    user_id: UserID,
    product_name: ProductName,
):
    mock_task_manager = create_mock_task_manager(status_or_exception)

    status = await _celery_task_status(
        job_creation_task_id=job_creation_task_id,
        task_manager=mock_task_manager,
        user_id=user_id,
        product_name=product_name,
    )

    if job_creation_task_id is None:
        assert status == FunctionJobCreationTaskStatus.NOT_YET_SCHEDULED
    elif isinstance(status_or_exception, TaskNotFoundError):
        assert status == FunctionJobCreationTaskStatus.ERROR
    elif isinstance(status_or_exception, TaskStatus):
        assert status == FunctionJobCreationTaskStatus[status_or_exception.task_state.name]
    else:
        pytest.fail("Unexpected test input")
