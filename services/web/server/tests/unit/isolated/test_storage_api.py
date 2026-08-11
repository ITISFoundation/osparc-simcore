# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any

import pytest
from aiohttp import web
from celery_library.errors import encode_celery_transferable_error
from faker import Faker
from models_library.api_schemas_async_jobs.exceptions import JobError
from models_library.celery import TaskState, TaskStatus, TaskUUID
from models_library.products import ProductName
from models_library.progress_bar import ProgressReport
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from pytest_mock import MockerFixture, MockType
from servicelib.celery.task_manager import TaskManager
from simcore_service_webserver.storage.api import (
    delete_project_data_folders,
    delete_project_node_data_folders,
    get_task_manager,
)


@pytest.fixture
def app() -> web.Application:
    return web.Application()


@pytest.fixture
def user_id(faker: Faker) -> UserID:
    return faker.pyint(min_value=1)


@pytest.fixture
def product_name(faker: Faker) -> ProductName:
    return faker.word()


@pytest.fixture
def project_id(faker: Faker) -> ProjectID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def node_id(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


def _mock_task_manager(
    mocker: MockerFixture,
    *,
    faker: Faker,
    task_state: TaskState,
    task_result: Any,
) -> MockType:
    task_uuid: TaskUUID = faker.uuid4(cast_to=None)
    task_manager = mocker.AsyncMock(spec=TaskManager)
    task_manager.submit_task.return_value = task_uuid
    task_manager.get_status.return_value = TaskStatus(
        task_uuid=task_uuid,
        task_state=task_state,
        progress_report=ProgressReport(actual_value=1.0, total=1.0),
    )
    task_manager.get_result.return_value = task_result
    mocker.patch(
        get_task_manager.__name__,
        autospec=True,
        return_value=task_manager,
    )
    return task_manager


async def test_delete_project_data_folders_succeeds(
    mocker: MockerFixture,
    faker: Faker,
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
    project_id: ProjectID,
):
    task_manager = _mock_task_manager(mocker, faker=faker, task_state=TaskState.SUCCESS, task_result=None)

    await delete_project_data_folders(app, product_name=product_name, user_id=user_id, project_id=project_id)

    assert task_manager.submit_task.called


async def test_delete_project_data_folders_raises_on_task_failure(
    mocker: MockerFixture,
    faker: Faker,
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
    project_id: ProjectID,
):
    # regression: a failed deletion task must not be silently ignored
    _mock_task_manager(
        mocker,
        faker=faker,
        task_state=TaskState.FAILURE,
        task_result=encode_celery_transferable_error(ValueError("could not delete project folders")),
    )

    with pytest.raises(JobError) as err_info:
        await delete_project_data_folders(app, product_name=product_name, user_id=user_id, project_id=project_id)

    assert ValueError.__name__ in f"{err_info.value}"
    assert "could not delete project folders" in f"{err_info.value}"


async def test_delete_project_node_data_folders_succeeds(
    mocker: MockerFixture,
    faker: Faker,
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
    project_id: ProjectID,
    node_id: NodeID,
):
    task_manager = _mock_task_manager(mocker, faker=faker, task_state=TaskState.SUCCESS, task_result=None)

    await delete_project_node_data_folders(
        app, product_name=product_name, user_id=user_id, project_id=project_id, node_id=node_id
    )

    assert task_manager.submit_task.called


async def test_delete_project_node_data_folders_raises_on_task_failure(
    mocker: MockerFixture,
    faker: Faker,
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
    project_id: ProjectID,
    node_id: NodeID,
):
    _mock_task_manager(
        mocker,
        faker=faker,
        task_state=TaskState.FAILURE,
        task_result=encode_celery_transferable_error(ValueError("could not delete node folders")),
    )

    with pytest.raises(JobError) as err_info:
        await delete_project_node_data_folders(
            app, product_name=product_name, user_id=user_id, project_id=project_id, node_id=node_id
        )

    assert ValueError.__name__ in f"{err_info.value}"
    assert "could not delete node folders" in f"{err_info.value}"
