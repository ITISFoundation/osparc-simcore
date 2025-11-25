# pylint:disable=redefined-outer-name

import datetime
from collections.abc import AsyncIterable, Callable
from contextlib import AbstractAsyncContextManager

import pytest
from pydantic import TypeAdapter
from servicelib.long_running_tasks._redis_store import (
    _MARKED_FOR_REMOVAL_AT_FIELD,
    RedisStore,
)
from servicelib.long_running_tasks.models import TaskData
from servicelib.redis._client import RedisClientSDK
from settings_library.redis import RedisDatabase, RedisSettings
from utils import without_marked_for_removal_at


def test_ensure_task_data_field_name_and_type():
    # NOTE: ensure thse do not change, if you want to change them remeber that the db is invalid
    assert _MARKED_FOR_REMOVAL_AT_FIELD == "marked_for_removal_at"
    field = TaskData.model_fields[_MARKED_FOR_REMOVAL_AT_FIELD]
    assert field.annotation == datetime.datetime | None


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
) -> AsyncIterable[RedisStore]:
    store = RedisStore(redis_settings=use_in_memory_redis, lrt_namespace="test")

    await store.setup()
    yield store
    await store.shutdown()

    # triggers cleanup of all redis data
    async with get_redis_client_sdk(RedisDatabase.LONG_RUNNING_TASKS):
        pass


async def test_workflow(store: RedisStore, task_data: TaskData) -> None:
    # task data
    assert await store.list_tasks_data() == []
    assert await store.get_task_data("missing") is None

    await store.add_task_data(task_data.task_id, task_data)

    assert await store.list_tasks_data() == [task_data]

    await store.delete_task_data(task_data.task_id)

    assert await store.list_tasks_data() == []

    # cancelled tasks
    await store.add_task_data(task_data.task_id, task_data)

    assert await store.is_marked_for_removal(task_data.task_id) is False

    await store.mark_for_removal(task_data.task_id)

    assert await store.is_marked_for_removal(task_data.task_id) is True


@pytest.fixture
async def redis_stores(
    use_in_memory_redis: RedisSettings,
    get_redis_client_sdk: Callable[
        [RedisDatabase], AbstractAsyncContextManager[RedisClientSDK]
    ],
) -> AsyncIterable[list[RedisStore]]:
    stores: list[RedisStore] = [
        RedisStore(redis_settings=use_in_memory_redis, lrt_namespace=f"test-{i}")
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

    for store in redis_stores:
        await store.add_task_data(task_data.task_id, task_data)
        await store.mark_for_removal(task_data.task_id)

    for store in redis_stores:
        assert [
            without_marked_for_removal_at(x) for x in await store.list_tasks_data()
        ] == [task_data]

    for store in redis_stores:
        await store.delete_task_data(task_data.task_id)

    for store in redis_stores:
        assert await store.list_tasks_data() == []
