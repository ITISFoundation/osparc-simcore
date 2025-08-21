from collections.abc import Callable

import pytest
from faker import Faker
from pytest_mock import MockerFixture, MockType
from servicelib.celery.models import TaskStatus, TaskUUID
from servicelib.celery.task_manager import Task, TaskManager

_faker = Faker()


@pytest.fixture
def mock_task_manager_object(mocker: MockerFixture) -> MockType:
    """
    Returns a TaskManager mock with example return values for each method.
    """
    mock = mocker.Mock(spec=TaskManager)

    # Example return values (replace with realistic objects as needed)
    mock.submit_task.return_value = TaskUUID(_faker.uuid4())
    mock.cancel_task.return_value = None
    mock.get_task_result.return_value = {"result": "example"}
    status_extra = TaskStatus.model_config.get("json_schema_extra")
    assert status_extra is not None
    status_examples = status_extra.get("examples")
    assert isinstance(status_examples, list)
    assert len(status_examples) > 0
    mock.get_task_status.return_value = TaskStatus.model_validate(status_examples[0])
    list_extra = Task.model_config.get("json_schema_extra")
    assert isinstance(list_extra, dict)
    list_examples = list_extra.get("examples")
    assert isinstance(list_examples, list)
    assert len(list_examples) > 0
    mock.list_tasks.return_value = [
        Task.model_validate(example) for example in list_examples
    ]
    mock.set_task_progress.return_value = None
    return mock


@pytest.fixture
def mock_task_manager_raising_factory(
    mocker: MockerFixture,
) -> Callable[[Exception], MockType]:
    def _factory(task_manager_exception: Exception) -> MockType:
        mock = mocker.Mock(spec=TaskManager)

        def _raise_exc(*args, **kwargs):
            raise task_manager_exception

        mock.submit_task.side_effect = _raise_exc
        mock.cancel_task.side_effect = _raise_exc
        mock.get_task_result.side_effect = _raise_exc
        mock.get_task_status.side_effect = _raise_exc
        mock.list_tasks.side_effect = _raise_exc
        mock.set_task_progress.side_effect = _raise_exc
        return mock

    return _factory
