import pytest
from models_library.api_schemas_long_running_tasks.tasks import TaskGet
from pydantic import TypeAdapter


def _get_data_without_task_name(task_id: str) -> dict:
    return {
        "task_id": task_id,
        "status_href": "",
        "result_href": "",
        "abort_href": "",
    }


@pytest.mark.parametrize(
    "data, expected_task_name",
    [
        (_get_data_without_task_name("a.b.c.d"), "b"),
        (_get_data_without_task_name("a.b.c"), "b"),
        (_get_data_without_task_name("a.b"), "b"),
        (_get_data_without_task_name("a"), "a"),
    ],
)
def test_try_extract_task_name(data: dict, expected_task_name: str) -> None:
    task_get = TaskGet(**data)
    assert task_get.task_name == expected_task_name

    task_get = TypeAdapter(TaskGet).validate_python(data)
    assert task_get.task_name == expected_task_name


def _get_data_with_task_name(task_id: str, task_name: str) -> dict:
    return {
        "task_id": task_id,
        "task_name": task_name,
        "status_href": "",
        "result_href": "",
        "abort_href": "",
    }


@pytest.mark.parametrize(
    "data, expected_task_name",
    [
        (_get_data_with_task_name("a.b.c.d", "a_name"), "a_name"),
        (_get_data_with_task_name("a.b.c", "a_name"), "a_name"),
        (_get_data_with_task_name("a.b", "a_name"), "a_name"),
        (_get_data_with_task_name("a", "a_name"), "a_name"),
    ],
)
def test_task_name_is_provided(data: dict, expected_task_name: str) -> None:
    task_get = TaskGet(**data)
    assert task_get.task_name == expected_task_name

    task_get = TypeAdapter(TaskGet).validate_python(data)
    assert task_get.task_name == expected_task_name
