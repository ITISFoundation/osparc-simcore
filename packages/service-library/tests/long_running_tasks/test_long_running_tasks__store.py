# pylint:disable=redefined-outer-name

from collections.abc import AsyncIterable, Callable
from contextlib import AbstractAsyncContextManager

import pytest
from pydantic import TypeAdapter
from servicelib.long_running_tasks._store.base import BaseStore
from servicelib.long_running_tasks._store.redis import RedisStore
from servicelib.long_running_tasks.models import TaskData
from servicelib.redis._client import RedisClientSDK
from settings_library.redis import RedisDatabase, RedisSettings


@pytest.fixture
def task_data() -> TaskData:
    return TypeAdapter(TaskData).validate_python(
        TaskData.model_json_schema()["examples"][0]
    )


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


async def test_workflow(store: BaseStore, task_data: TaskData) -> None:
    # task data
    assert await store.list_tasks_data() == []
    assert await store.get_task_data("missing") is None

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
    redis_stores: list[RedisStore], task_data: TaskData
):

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
