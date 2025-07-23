# pylint:disable=redefined-outer-name

from collections.abc import AsyncIterable, Callable
from contextlib import AbstractAsyncContextManager

import pytest
from faker import Faker
from models_library.api_schemas_long_running_tasks.base import TaskProgress
from pydantic import TypeAdapter
from servicelib.long_running_tasks._store.base import BaseStore
from servicelib.long_running_tasks._store.in_memory import InMemoryStore
from servicelib.long_running_tasks._store.redis import RedisStore
from servicelib.long_running_tasks.models import TaskData
from servicelib.redis._client import RedisClientSDK
from settings_library.redis import RedisDatabase, RedisSettings

pytest_simcore_core_services_selection = [
    "redis",
]
pytest_simcore_ops_services_selection = [
    "redis-commander",
]


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
                "task_context": {"key": "value"},
                "fire_and_forget": faker.boolean(),
            }
        )

    return _


@pytest.fixture(params=[InMemoryStore, RedisStore])
async def store(
    redis_service: RedisSettings,
    request: pytest.FixtureRequest,
    get_redis_client_sdk: Callable[
        [RedisDatabase], AbstractAsyncContextManager[RedisClientSDK]
    ],
) -> AsyncIterable[BaseStore]:
    store: BaseStore | None = None
    match request.param.__name__:
        case InMemoryStore.__name__:
            store = InMemoryStore()

        case RedisStore.__name__:
            store = RedisStore(redis_settings=redis_service, namespace="test")

    if store is None:
        msg = f"Unsupported store type: {request.param}"
        raise ValueError(msg)

    await store.setup()
    yield store
    await store.teardown()

    # triggers cleanup of all redis data
    async with get_redis_client_sdk(RedisDatabase.LONG_RUNNING_TASKS):
        pass


async def test_workflow(
    store: BaseStore, get_task_data: Callable[[], TaskData]
) -> None:
    # task data
    assert await store.list_tasks_data() == []
    assert await store.get_task_data("missing") is None

    task_data = get_task_data()
    await store.set_task_data(task_data.task_id, task_data)

    assert await store.list_tasks_data() == [task_data]

    await store.delete_task_data(task_data.task_id)

    assert await store.list_tasks_data() == []

    # cancelled tasks
    assert await store.get_cancelled() == {}

    await store.set_as_cancelled(task_data.task_id, task_data.task_context)

    assert await store.get_cancelled() == {task_data.task_id: task_data.task_context}
