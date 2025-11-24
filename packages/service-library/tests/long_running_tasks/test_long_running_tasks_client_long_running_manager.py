# pylint:disable=redefined-outer-name

from collections.abc import AsyncIterable, Callable
from contextlib import AbstractAsyncContextManager
from copy import deepcopy

import pytest
from faker import Faker
from pydantic import TypeAdapter
from servicelib.long_running_tasks._redis_store import RedisStore
from servicelib.long_running_tasks.long_running_client_helper import (
    LongRunningClientHelper,
)
from servicelib.long_running_tasks.models import LRTNamespace, TaskData
from servicelib.redis._client import RedisClientSDK
from settings_library.redis import RedisDatabase, RedisSettings
from utils import without_marked_for_removal_at


@pytest.fixture
def task_data() -> TaskData:
    return TypeAdapter(TaskData).validate_python(
        TaskData.model_json_schema()["examples"][0]
    )


@pytest.fixture
def lrt_namespace(faker: Faker) -> LRTNamespace:
    return TypeAdapter(LRTNamespace).validate_python(f"test-namespace:{faker.uuid4()}")


@pytest.fixture
async def store(
    use_in_memory_redis: RedisSettings,
    get_redis_client_sdk: Callable[
        [RedisDatabase], AbstractAsyncContextManager[RedisClientSDK]
    ],
    lrt_namespace: LRTNamespace,
) -> AsyncIterable[RedisStore]:
    store = RedisStore(redis_settings=use_in_memory_redis, lrt_namespace=lrt_namespace)

    await store.setup()
    yield store
    await store.shutdown()

    # triggers cleanup of all redis data
    async with get_redis_client_sdk(RedisDatabase.LONG_RUNNING_TASKS):
        pass


@pytest.fixture
async def long_running_client_helper(
    use_in_memory_redis: RedisSettings,
) -> AsyncIterable[LongRunningClientHelper]:
    helper = LongRunningClientHelper(redis_settings=use_in_memory_redis)

    await helper.setup()
    yield helper
    await helper.shutdown()


async def test_cleanup_namespace(
    store: RedisStore,
    task_data: TaskData,
    long_running_client_helper: LongRunningClientHelper,
    lrt_namespace: LRTNamespace,
) -> None:
    # create entries in both sides
    await store.add_task_data(task_data.task_id, task_data)
    await store.mark_for_removal(task_data.task_id)

    # entries exit
    marked_for_removal = deepcopy(task_data)
    marked_for_removal.marked_for_removal = True
    assert [
        without_marked_for_removal_at(x) for x in await store.list_tasks_data()
    ] == [marked_for_removal]

    # removes
    await long_running_client_helper.cleanup(lrt_namespace)

    # entris were removed
    assert await store.list_tasks_data() == []

    # ensore it does not raise errors if there is nothing to remove
    await long_running_client_helper.cleanup(lrt_namespace)
