# pylint:disable=redefined-outer-name

from collections.abc import Callable

import pytest
from faker import Faker
from models_library.api_schemas_long_running_tasks.base import TaskProgress
from pydantic import TypeAdapter
from servicelib.long_running_tasks._store.base import BaseStore
from servicelib.long_running_tasks._store.in_memory import InMemoryStore
from servicelib.long_running_tasks.models import TaskData


@pytest.fixture
def get_task_data(faker: Faker) -> Callable[[], TaskData]:
    def _() -> TaskData:
        task_id = faker.uuid4()
        return TypeAdapter(TaskData).validate_python(
            {
                "task_id": task_id,
                "task_name": faker.word(),
                "task_status": faker.random_element(
                    elements=("running", "completed", "failed")
                ),
                "task_progress": TaskProgress.create(task_id),
                "task_context": faker.pydict(),
                "fire_and_forget": faker.boolean(),
            }
        )

    return _


@pytest.fixture(params=[InMemoryStore.__name__])
async def store(request: pytest.FixtureRequest) -> BaseStore:
    match request.param:
        case InMemoryStore.__name__:
            return InMemoryStore()

    msg = f"Unsupported store type: {request.param}"
    raise ValueError(msg)


async def test_workflow(
    store: BaseStore, get_task_data: Callable[[], TaskData]
) -> None:
    # task data
    assert await store.list_tasks_data() == []

    task_data = get_task_data()
    await store.set_task_data(task_data.task_id, task_data)

    assert await store.list_tasks_data() == [task_data]

    await store.delete_task_data(task_data.task_id)

    assert await store.list_tasks_data() == []

    # cancelled tasks
    assert await store.get_cancelled() == {}

    await store.set_as_cancelled(task_data.task_id, task_data.task_context)

    assert await store.get_cancelled() == {task_data.task_id: task_data.task_context}
