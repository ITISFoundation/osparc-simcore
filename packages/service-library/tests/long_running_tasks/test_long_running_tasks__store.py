# pylint:disable=redefined-outer-name

from collections.abc import AsyncIterable, Callable
from contextlib import AbstractAsyncContextManager

import pytest
from faker import Faker
from models_library.api_schemas_long_running_tasks.base import TaskProgress
from pydantic import TypeAdapter
from servicelib.long_running_tasks._store.base import BaseStore
from servicelib.long_running_tasks._store.redis import RedisStore
from servicelib.long_running_tasks.models import TaskData
from servicelib.redis._client import RedisClientSDK
from settings_library.redis import RedisDatabase, RedisSettings


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


@pytest.fixture
async def store(
    use_in_memory_redis: RedisSettings,
    get_redis_client_sdk: Callable[
        [RedisDatabase], AbstractAsyncContextManager[RedisClientSDK]
    ],
) -> AsyncIterable[BaseStore]:
    store = RedisStore(redis_settings=use_in_memory_redis, namespace="test")

    await store.setup()
    yield store
    await store.shutdown()

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


@pytest.fixture
async def redis_stores(
    use_in_memory_redis: RedisSettings,
    get_redis_client_sdk: Callable[
        [RedisDatabase], AbstractAsyncContextManager[RedisClientSDK]
    ],
) -> AsyncIterable[list[RedisStore]]:
    stores: list[RedisStore] = [
        RedisStore(redis_settings=use_in_memory_redis, namespace=f"test-{i}")
        for i in range(5)
    ]
    for store in stores:
        await store.setup()

    yield stores

    for store in stores:
        await store.shutdown()

    # triggers cleanup of all redis data
    async with get_redis_client_sdk(RedisDatabase.LONG_RUNNING_TASKS):
        pass


async def test_workflow_multiple_redis_stores_with_different_namespaces(
    redis_stores: list[RedisStore], get_task_data: Callable[[], TaskData]
):
    task_data = get_task_data()

    for store in redis_stores:
        assert await store.list_tasks_data() == []
        assert await store.get_cancelled() == {}

    for store in redis_stores:
        await store.set_task_data(task_data.task_id, task_data)
        await store.set_as_cancelled(task_data.task_id, None)

    for store in redis_stores:
        assert await store.list_tasks_data() == [task_data]
        assert await store.get_cancelled() == {task_data.task_id: None}

    for store in redis_stores:
        await store.delete_task_data(task_data.task_id)

    for store in redis_stores:
        assert await store.list_tasks_data() == []
