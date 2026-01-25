# pylint: disable=redefined-outer-name

from collections.abc import Callable

import pytest
from faker import Faker
from pydantic import TypeAdapter
from pytest_mock import MockerFixture, MockType
from servicelib.celery.models import TaskStatus, TaskUUID
from servicelib.celery.task_manager import Task, TaskManager

_faker = Faker()


@pytest.fixture
def submit_task_return_value() -> TaskUUID:
    return TypeAdapter(TaskUUID).validate_python(_faker.uuid4())


@pytest.fixture
def cancel_task_return_value() -> None:
    return None


@pytest.fixture
def get_task_result_return_value() -> dict:
    return {"result": "example"}


@pytest.fixture
def get_task_status_return_value() -> TaskStatus:
    example = TaskStatus.model_json_schema()["examples"][0]
    return TaskStatus.model_validate(example)


@pytest.fixture
def list_tasks_return_value() -> list[Task]:
    examples = Task.model_json_schema()["examples"]
    assert len(examples) > 0
    return [Task.model_validate(example) for example in examples]


@pytest.fixture
def set_task_progress_return_value() -> None:
    return None


@pytest.fixture
def mock_task_manager_object(
    mocker: MockerFixture,
    submit_task_return_value: TaskUUID,
    cancel_task_return_value: None,
    get_task_result_return_value: dict,
    get_task_status_return_value: TaskStatus,
    list_tasks_return_value: list[Task],
    set_task_progress_return_value: None,
) -> MockType:
    """
    Returns a TaskManager mock with overridable return values for each method.
    If a return value is an Exception, the method will raise it.
    """
    mock = mocker.Mock(spec=TaskManager)

    def _set_return_or_raise(method, value):
        if isinstance(value, Exception):
            method.side_effect = lambda: (_ for _ in ()).throw(value)
        else:
            method.return_value = value

    _set_return_or_raise(mock.submit_task, submit_task_return_value)
    _set_return_or_raise(mock.cancel_task, cancel_task_return_value)
    _set_return_or_raise(mock.get_task_result, get_task_result_return_value)
    _set_return_or_raise(mock.get_task_status, get_task_status_return_value)
    _set_return_or_raise(mock.list_tasks, list_tasks_return_value)
    _set_return_or_raise(mock.set_task_progress, set_task_progress_return_value)
    return mock


@pytest.fixture
def mock_task_manager_object_raising_factory(
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
