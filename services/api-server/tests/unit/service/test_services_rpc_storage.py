# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any

import pytest
from celery_library.errors import encode_celery_transferable_error
from faker import Faker
from models_library.api_schemas_async_jobs.exceptions import JobError
from models_library.celery import TaskState, TaskStatus, TaskUUID
from models_library.products import ProductName
from models_library.progress_bar import ProgressReport
from models_library.projects import ProjectID
from models_library.users import UserID
from pytest_mock import MockerFixture, MockType
from servicelib.celery.task_manager import TaskManager
from simcore_service_api_server.services_rpc.storage import StorageService


@pytest.fixture
def task_uuid(faker: Faker) -> TaskUUID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def project_id(faker: Faker) -> ProjectID:
    return faker.uuid4(cast_to=None)


def _mocked_task_manager(
    mocker: MockerFixture,
    *,
    task_uuid: TaskUUID,
    task_state: TaskState,
    task_result: Any,
) -> MockType:
    task_manager = mocker.AsyncMock(spec=TaskManager)
    task_manager.submit_task.return_value = task_uuid
    task_manager.get_status.return_value = TaskStatus(
        task_uuid=task_uuid,
        task_state=task_state,
        progress_report=ProgressReport(actual_value=1.0, total=1.0),
    )
    task_manager.get_result.return_value = task_result
    return task_manager


async def test_delete_project_s3_assets_succeeds(
    mocker: MockerFixture,
    task_uuid: TaskUUID,
    project_id: ProjectID,
    user_id: UserID,
    product_name: ProductName,
):
    task_manager = _mocked_task_manager(
        mocker,
        task_uuid=task_uuid,
        task_state=TaskState.SUCCESS,
        task_result=None,
    )
    storage_service = StorageService(_task_manager=task_manager, _user_id=user_id, _product_name=product_name)

    await storage_service.delete_project_s3_assets(project_id=project_id)

    assert task_manager.submit_task.called


async def test_delete_project_s3_assets_raises_on_task_failure(
    mocker: MockerFixture,
    task_uuid: TaskUUID,
    project_id: ProjectID,
    user_id: UserID,
    product_name: ProductName,
):
    # regression: a failed deletion task must not be silently ignored
    task_manager = _mocked_task_manager(
        mocker,
        task_uuid=task_uuid,
        task_state=TaskState.FAILURE,
        task_result=encode_celery_transferable_error(ValueError("could not delete project assets")),
    )
    storage_service = StorageService(_task_manager=task_manager, _user_id=user_id, _product_name=product_name)

    with pytest.raises(JobError) as err_info:
        await storage_service.delete_project_s3_assets(project_id=project_id)

    assert err_info.value.exc_type == ValueError.__name__
    assert "could not delete project assets" in err_info.value.exc_msg
