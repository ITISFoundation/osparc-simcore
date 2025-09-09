# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import AsyncIterable
from typing import Any

import pytest
from faker import Faker
from servicelib.deferred_tasks import TaskUID
from servicelib.redis._utils import handle_redis_returns_union_types
from settings_library.redis import RedisSettings
from simcore_service_dynamic_scheduler.services.generic_scheduler._models import (
    OperationErrorType,
    ScheduleId,
    StepStatus,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._store import (
    ScheduleDataStoreProxy,
    StepStoreProxy,
    Store,
)


@pytest.fixture
async def store(use_in_memory_redis: RedisSettings) -> AsyncIterable[Store]:
    store = Store(use_in_memory_redis)
    await store.setup()
    yield store
    await store._redis.client().flushall()  # noqa: SLF001
    await store.shutdown()


async def _assert_keys(store: Store, expected_keys: set[str]) -> None:
    keys = set(await store._redis.keys())  # noqa: SLF001
    assert keys == expected_keys


async def _assert_keys_in_hash(
    store: Store, hash_key: str, expected_keys: set[str]
) -> None:
    keys = set(
        await handle_redis_returns_union_types(
            store._redis.hkeys(hash_key)  # noqa: SLF001
        )
    )
    assert keys == expected_keys


async def test_store_workflow(store: Store):
    # save single value
    await store.set("hash1", "key1", "value1")
    await _assert_keys(store, {"hash1"})
    await _assert_keys_in_hash(store, "hash1", {"key1"})
    assert await store.get("hash1", "key1") == ("value1",)
    assert await store.get("hash1", "key1", "key1") == ("value1", "value1")
    assert await store.get("hash1", "missing1", "missing2") == (None, None)

    # remove last key in hash
    await store.delete("hash1", "key1")
    await _assert_keys(store, set())
    await _assert_keys_in_hash(store, "hash1", set())
    assert await store.get("hash1", "key1") == (None,)

    # save multiple values
    await store.set_multiple("hash2", {"key1": "value1", "key2": 2, "key3": True})
    await _assert_keys(store, {"hash2"})
    await _assert_keys_in_hash(store, "hash2", {"key1", "key2", "key3"})
    assert await store.get("hash2", "key1", "key2", "key3") == ("value1", 2, True)

    # delete a few keys form hash
    await store.delete("hash2", "key1", "key3", "missing1", "missing2", "missing3")
    await _assert_keys(store, {"hash2"})
    await _assert_keys_in_hash(store, "hash2", {"key2"})
    assert await store.get("hash2", "key1", "key2", "key3") == (None, 2, None)

    # increase a key in the hahs
    assert await store.increase_and_get("hash2", "key4") == 1
    assert await store.increase_and_get("hash2", "key4") == 2
    assert await store.increase_and_get("hash2", "key4") == 3
    assert await store.increase_and_get("hash2", "key4") == 4

    # remove hash completely
    await store.remove("hash2")
    await _assert_keys(store, set())
    await _assert_keys_in_hash(store, "hash2", set())
    assert await store.get("hash2", "key1", "key2", "key3") == (None, None, None)


@pytest.mark.parametrize(
    "value",
    [
        1,
        "a",
        3.14,
        True,
        None,
        {"dict": "with_data"},
    ],
)
async def test_store_supporse_multiple_python_base_types(store: Store, value: Any):
    # values are stored and recovered in their original type
    await store.set("hash1", "key1", value)
    assert (await store.get("hash1", "key1")) == (value,)


@pytest.fixture
def schedule_id(faker: Faker) -> ScheduleId:
    return faker.uuid4()


async def test_schedule_data_store_proxy_workflow(
    store: Store, schedule_id: ScheduleId
):
    proxy = ScheduleDataStoreProxy(store=store, schedule_id=schedule_id)
    hash_key = f"SCH:{schedule_id}"

    # set
    await proxy.set("operation_name", "op1")
    await proxy.set("group_index", 1)
    await proxy.set("is_creating", value=True)
    await _assert_keys(store, {hash_key})
    await _assert_keys_in_hash(
        store, hash_key, {"operation_name", "group_index", "is_creating"}
    )

    # get
    assert await proxy.get("operation_name") == "op1"
    assert await proxy.get("group_index") == 1
    assert await proxy.get("is_creating") is True

    # remove
    await proxy.delete("operation_name", "is_creating", "group_index")
    await _assert_keys(store, set())
    await _assert_keys_in_hash(store, hash_key, set())

    # set multiple
    await proxy.set_multiple(
        {
            "group_index": 2,
            "is_creating": False,
            "operation_error_type": OperationErrorType.STEP_ISSUE,
            "operation_error_message": "mock_error_message",
        }
    )
    await _assert_keys(store, {hash_key})
    await _assert_keys_in_hash(
        store,
        hash_key,
        {
            "group_index",
            "is_creating",
            "operation_error_type",
            "operation_error_message",
        },
    )

    # remove all keys an even missing ones
    await proxy.delete(
        "operation_name",
        "is_creating",
        "group_index",
        "operation_error_type",
        "operation_error_message",
    )
    await _assert_keys(store, set())
    await _assert_keys_in_hash(store, hash_key, set())


@pytest.mark.parametrize("is_creating", [True, False])
@pytest.mark.parametrize("use_remove", [True, False])
async def test_step_store_proxy_workflow(
    store: Store, schedule_id: ScheduleId, is_creating: bool, use_remove: bool
):
    proxy = StepStoreProxy(
        store=store,
        schedule_id=schedule_id,
        operation_name="op1",
        step_group_name="sg1",
        step_name="step",
        is_creating=is_creating,
    )
    is_creating_str = "C" if is_creating else "D"
    hash_key = f"SCH:{schedule_id}:STEPS:op1:sg1:{is_creating_str}:step"

    # set
    await proxy.set("status", StepStatus.RUNNING)
    await _assert_keys(store, {hash_key})
    await _assert_keys_in_hash(store, hash_key, {"status"})

    # get
    assert await proxy.get("status") == StepStatus.RUNNING

    # remove
    await proxy.delete("status")
    await _assert_keys(store, set())
    await _assert_keys_in_hash(store, hash_key, set())

    # set multiple
    await proxy.set_multiple(
        {
            "status": StepStatus.SUCCESS,
            "deferred_task_uid": TaskUID("mytask"),
            "error_traceback": "mock_traceback",
            "requires_manual_intervention": True,
        }
    )
    await _assert_keys(store, {hash_key})
    await _assert_keys_in_hash(
        store,
        hash_key,
        {
            "status",
            "deferred_task_uid",
            "error_traceback",
            "requires_manual_intervention",
        },
    )

    # remove all keys an even missing ones
    if use_remove:
        await proxy.remove()
    else:
        await proxy.delete(
            "status",
            "deferred_task_uid",
            "error_traceback",
            "requires_manual_intervention",
        )
    await _assert_keys(store, set())
    await _assert_keys_in_hash(store, hash_key, set())
