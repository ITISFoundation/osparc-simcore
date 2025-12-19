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
    ProvidedOperationContext,
    ScheduleId,
    StepStatus,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._store import (
    EventType,
    OperationContext,
    OperationContextProxy,
    OperationEventsProxy,
    OperationRemovalProxy,
    ScheduleDataStoreProxy,
    StepGroupProxy,
    StepStoreProxy,
    Store,
    _get_group_hash_key,
    _get_operation_context_hash_key,
    _get_scheduler_data_hash_key,
    _get_step_hash_key,
)


@pytest.fixture
def schedule_id(faker: Faker) -> ScheduleId:
    return faker.uuid4()


@pytest.fixture
async def store(use_in_memory_redis: RedisSettings) -> AsyncIterable[Store]:
    store = Store(use_in_memory_redis)
    await store.setup()
    yield store
    await store.redis.client().flushall()
    await store.shutdown()


async def _assert_keys(store: Store, expected_keys: set[str]) -> None:
    keys = set(await store.redis.keys())
    assert keys == expected_keys


async def _assert_keys_in_hash(
    store: Store, hash_key: str, expected_keys: set[str]
) -> None:
    keys = set(await handle_redis_returns_union_types(store.redis.hkeys(hash_key)))
    assert keys == expected_keys


def test_ensure_keys_have_the_same_prefix(schedule_id: ScheduleId):
    key_prefix = f"SCH:{schedule_id}"

    assert key_prefix == _get_scheduler_data_hash_key(schedule_id=schedule_id)

    keys: list[str] = [
        _get_scheduler_data_hash_key(schedule_id=schedule_id),
        _get_step_hash_key(
            schedule_id=schedule_id,
            operation_name="op1",
            group_name="sg1",
            step_name="step1",
            is_executing=True,
        ),
        _get_group_hash_key(
            schedule_id=schedule_id,
            operation_name="op1",
            group_name="sg1",
            is_executing=True,
        ),
        _get_operation_context_hash_key(
            schedule_id=schedule_id,
            operation_name="op1",
        ),
    ]

    for key in keys:
        assert key.startswith(key_prefix)


async def test_store_workflow(store: Store):
    # save single value
    await store.set_key_in_hash("hash1", "key1", "value1")
    await _assert_keys(store, {"hash1"})
    await _assert_keys_in_hash(store, "hash1", {"key1"})
    assert await store.get_keys_from_hash("hash1", "key1") == ("value1",)
    assert await store.get_keys_from_hash("hash1", "key1", "key1") == (
        "value1",
        "value1",
    )
    assert await store.get_keys_from_hash("hash1", "missing1", "missing2") == (
        None,
        None,
    )

    # remove last key in hash
    await store.delete_key_from_hash("hash1", "key1")
    await _assert_keys(store, set())
    await _assert_keys_in_hash(store, "hash1", set())
    assert await store.get_keys_from_hash("hash1", "key1") == (None,)

    # save multiple values
    await store.set_keys_in_hash("hash2", {"key1": "value1", "key2": 2, "key3": True})
    await _assert_keys(store, {"hash2"})
    await _assert_keys_in_hash(store, "hash2", {"key1", "key2", "key3"})
    assert await store.get_keys_from_hash("hash2", "key1", "key2", "key3") == (
        "value1",
        2,
        True,
    )

    # delete a few keys form hash
    await store.delete_key_from_hash(
        "hash2", "key1", "key3", "missing1", "missing2", "missing3"
    )
    await _assert_keys(store, {"hash2"})
    await _assert_keys_in_hash(store, "hash2", {"key2"})
    assert await store.get_keys_from_hash("hash2", "key1", "key2", "key3") == (
        None,
        2,
        None,
    )

    # increase a key in the hahs
    assert await store.increase_key_in_hash_and_get("hash2", "key4") == 1
    assert await store.increase_key_in_hash_and_get("hash2", "key4") == 2
    assert await store.increase_key_in_hash_and_get("hash2", "key4") == 3
    assert await store.increase_key_in_hash_and_get("hash2", "key4") == 4

    # remove hash completely
    await store.delete("hash2")
    await _assert_keys(store, set())
    await _assert_keys_in_hash(store, "hash2", set())
    assert await store.get_keys_from_hash("hash2", "key1", "key2", "key3") == (
        None,
        None,
        None,
    )


@pytest.mark.parametrize(
    "value",
    [
        1,
        "a",
        3.14,
        True,
        None,
        {"dict": "with_data"},
        [1, 2, 3],
    ],
)
async def test_store_supporse_multiple_python_base_types(store: Store, value: Any):
    # values are stored and recovered in their original type
    await store.set_key_in_hash("hash1", "key1", value)
    assert (await store.get_keys_from_hash("hash1", "key1")) == (value,)


async def test_schedule_data_store_proxy(store: Store, schedule_id: ScheduleId):
    proxy = ScheduleDataStoreProxy(store=store, schedule_id=schedule_id)
    hash_key = f"SCH:{schedule_id}"

    # set
    await proxy.create_or_update("operation_name", "op1")
    await proxy.create_or_update("group_index", 1)
    await proxy.create_or_update("is_executing", value=True)
    await _assert_keys(store, {hash_key})
    await _assert_keys_in_hash(
        store, hash_key, {"operation_name", "group_index", "is_executing"}
    )

    # get
    assert await proxy.read("operation_name") == "op1"
    assert await proxy.read("group_index") == 1
    assert await proxy.read("is_executing") is True

    # remove
    await proxy.delete_keys("operation_name", "is_executing", "group_index")
    await _assert_keys(store, set())
    await _assert_keys_in_hash(store, hash_key, set())

    # set multiple
    await proxy.create_or_update_multiple(
        {
            "group_index": 2,
            "is_executing": False,
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
            "is_executing",
            "operation_error_type",
            "operation_error_message",
        },
    )

    # remove all keys an even missing ones
    await proxy.delete_keys(
        "operation_name",
        "is_executing",
        "group_index",
        "operation_error_type",
        "operation_error_message",
    )
    await _assert_keys(store, set())
    await _assert_keys_in_hash(store, hash_key, set())


@pytest.mark.parametrize("is_executing", [True, False])
@pytest.mark.parametrize("use_remove", [True, False])
async def test_steps_store_proxy(
    store: Store, schedule_id: ScheduleId, is_executing: bool, use_remove: bool
):
    proxy = StepStoreProxy(
        store=store,
        schedule_id=schedule_id,
        operation_name="op1",
        step_group_name="sg1",
        step_name="step",
        is_executing=is_executing,
    )
    is_executing_str = "E" if is_executing else "R"
    hash_key = f"SCH:{schedule_id}:STEPS:op1:sg1:{is_executing_str}:step"

    # set
    await proxy.create_or_update("status", StepStatus.RUNNING)
    await _assert_keys(store, {hash_key})
    await _assert_keys_in_hash(store, hash_key, {"status"})

    # get
    assert await proxy.read("status") == StepStatus.RUNNING

    # remove
    await proxy.delete_keys("status")
    await _assert_keys(store, set())
    await _assert_keys_in_hash(store, hash_key, set())

    # set multiple
    await proxy.create_or_update_multiple(
        {
            "status": StepStatus.SUCCESS,
            "deferred_task_uid": TaskUID("mytask"),
            "error_traceback": "mock_traceback",
            "requires_manual_intervention": True,
            "deferred_created": True,
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
            "deferred_created",
        },
    )

    # remove all keys an even missing ones
    if use_remove:
        await proxy.delete()
    else:
        await proxy.delete_keys(
            "status",
            "deferred_task_uid",
            "error_traceback",
            "requires_manual_intervention",
            "deferred_created",
        )
    await _assert_keys(store, set())
    await _assert_keys_in_hash(store, hash_key, set())


@pytest.mark.parametrize("is_executing", [True, False])
async def test_step_group_proxy(
    store: Store,
    schedule_id: ScheduleId,
    is_executing: bool,
):
    step_group_proxy = StepGroupProxy(
        store=store,
        schedule_id=schedule_id,
        operation_name="op1",
        step_group_name="sg1",
        is_executing=is_executing,
    )

    async def _get_steps_count() -> int | None:
        (response,) = await store.get_keys_from_hash(
            step_group_proxy._get_hash_key(),
            "done_steps",
        )
        return response

    assert await _get_steps_count() is None

    for _ in range(10):
        await step_group_proxy.increment_and_get_done_steps_count()
        assert await _get_steps_count() == 1
        await step_group_proxy.decrement_and_get_done_steps_count()
        assert await _get_steps_count() == 0

    await step_group_proxy.delete()
    assert await _get_steps_count() is None


@pytest.mark.parametrize(
    "provided_context",
    [
        {},
        {
            "k1": "v1",
            "k2": 2,
            "k3": True,
            "k4": None,
            "k5": 3.14,
            "k6": {"a": "b"},
            "k7": [1, 2, 3],
        },
    ],
)
async def test_operation_context_proxy(
    store: Store, schedule_id: ScheduleId, provided_context: ProvidedOperationContext
):
    proxy = OperationContextProxy(
        store=store, schedule_id=schedule_id, operation_name="op1"
    )
    hash_key = f"SCH:{schedule_id}:OP_CTX:op1"

    await _assert_keys(store, set())
    await _assert_keys_in_hash(store, hash_key, set())

    await proxy.create_or_update(provided_context)

    await _assert_keys(store, set() if len(provided_context) == 0 else {hash_key})
    await _assert_keys_in_hash(store, hash_key, set(provided_context.keys()))

    assert await proxy.read(*provided_context.keys()) == provided_context


async def test_operation_removal_proxy(store: Store, schedule_id: ScheduleId):
    await _assert_keys(store, set())

    proxy = ScheduleDataStoreProxy(store=store, schedule_id=schedule_id)
    await proxy.create_or_update_multiple(
        {
            "group_index": 1,
            "is_executing": True,
            "operation_error_type": OperationErrorType.STEP_ISSUE,
            "operation_error_message": "mock_error_message",
            "operation_name": "op1",
        }
    )

    proxy = StepStoreProxy(
        store=store,
        schedule_id=schedule_id,
        operation_name="op1",
        step_group_name="sg1",
        step_name="step",
        is_executing=True,
    )
    await proxy.create_or_update_multiple(
        {
            "deferred_created": True,
            "status": StepStatus.SUCCESS,
            "deferred_task_uid": TaskUID("mytask"),
            "requires_manual_intervention": True,
            "error_traceback": "mock_traceback",
        }
    )

    proxy = StepGroupProxy(
        store=store,
        schedule_id=schedule_id,
        operation_name="op1",
        step_group_name="sg1",
        is_executing=True,
    )
    await proxy.increment_and_get_done_steps_count()

    proxy = OperationContextProxy(
        store=store, schedule_id=schedule_id, operation_name="op1"
    )
    await proxy.create_or_update({"k1": "v1", "k2": 2})

    await _assert_keys(
        store,
        {
            f"SCH:{schedule_id}",
            f"SCH:{schedule_id}:GROUPS:op1:sg1:E",
            f"SCH:{schedule_id}:OP_CTX:op1",
            f"SCH:{schedule_id}:STEPS:op1:sg1:E:step",
        },
    )

    proxy = OperationRemovalProxy(store=store, schedule_id=schedule_id)
    await proxy.delete()
    await _assert_keys(store, set())

    # try to call when empty as well
    await proxy.delete()


async def test_operation_events_proxy(store: Store, schedule_id: ScheduleId):
    operation_name = "op1"
    initial_context: OperationContext = {"k1": "v1", "k2": 2}

    event_type = EventType.ON_EXECUTEDD_COMPLETED
    proxy = OperationEventsProxy(store, schedule_id, event_type)
    hash_key = f"SCH:{schedule_id}:EVENTS:{event_type}"

    assert await proxy.exists() is False
    await _assert_keys(store, set())
    await _assert_keys_in_hash(store, hash_key, set())

    await proxy.create_or_update_multiple(
        {"operation_name": operation_name, "initial_context": initial_context}
    )
    assert await proxy.exists() is True

    await _assert_keys(store, {hash_key})
    await _assert_keys_in_hash(store, hash_key, {"operation_name", "initial_context"})

    assert await proxy.read("operation_name") == operation_name
    assert await proxy.read("initial_context") == initial_context

    await proxy.delete()
    assert await proxy.exists() is False
    await _assert_keys(store, set())
    await _assert_keys_in_hash(store, hash_key, set())
