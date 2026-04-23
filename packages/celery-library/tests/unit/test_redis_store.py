# pylint: disable=redefined-outer-name

from collections.abc import AsyncIterator
from datetime import timedelta
from uuid import UUID

import pytest
from celery_library.backends import RedisTaskStore
from celery_library.backends._redis import (
    _build_redis_index_key_for_owner,
    _build_redis_task_or_group_key,
)
from faker import Faker
from models_library.celery import (
    Task,
    TaskExecutionMetadata,
)
from servicelib.redis import RedisClientSDK
from settings_library.redis import RedisDatabase, RedisSettings

_faker = Faker()

pytest_simcore_core_services_selection = ["redis"]
pytest_simcore_ops_services_selection = []


@pytest.fixture
async def redis_client_sdk(
    use_in_memory_redis: RedisSettings,
) -> AsyncIterator[RedisClientSDK]:
    redis_client_sdk = RedisClientSDK(
        use_in_memory_redis.build_redis_dsn(RedisDatabase.CELERY_TASKS),
        client_name="pytest_redis_store",
    )
    await redis_client_sdk.setup()
    try:
        yield redis_client_sdk
    finally:
        await redis_client_sdk.shutdown()


@pytest.fixture
async def redis_task_store(
    redis_client_sdk: RedisClientSDK,
) -> RedisTaskStore:
    return RedisTaskStore(redis_client_sdk)


async def test_list_tasks_uses_zset_index_not_scan(
    redis_task_store: RedisTaskStore,
    redis_client_sdk: RedisClientSDK,
    monkeypatch: pytest.MonkeyPatch,
):
    task_key = _faker.uuid4()

    await redis_task_store.create_task(
        task_key,
        TaskExecutionMetadata(name="my_task"),
        owner="test-svc",
        user_id=10001,
        product_name="osparc",
        expiry=timedelta(minutes=5),
    )

    def _forbid_scan_iter(*_args: object, **_kwargs: object) -> None:
        msg = "list_tasks must not use redis.scan_iter"
        raise AssertionError(msg)

    monkeypatch.setattr(
        redis_client_sdk.redis,
        "scan_iter",
        _forbid_scan_iter,
    )

    tasks = await redis_task_store.list_tasks(owner="test-svc", user_id=10001, product_name="osparc")
    assert len(tasks) == 1
    assert tasks[0].uuid == UUID(task_key)


async def test_list_tasks_filters_by_exact_owner_fields(
    redis_task_store: RedisTaskStore,
):
    owner = "test-svc"
    product = "osparc"
    user_id = 42
    expected_tasks: list[Task] = []

    # 5 tasks with same owner + product_name + user_id
    for _ in range(5):
        task_key = _faker.uuid4()
        await redis_task_store.create_task(
            task_key,
            TaskExecutionMetadata(name="my_task"),
            owner=owner,
            user_id=user_id,
            product_name=product,
            expiry=timedelta(minutes=5),
        )
        expected_tasks.append(
            Task(
                uuid=UUID(task_key),
                metadata=TaskExecutionMetadata(name="my_task"),
            )
        )

    # 3 tasks with a different user id
    for _ in range(3):
        task_key = _faker.uuid4()
        await redis_task_store.create_task(
            task_key,
            TaskExecutionMetadata(name="my_task"),
            owner=owner,
            user_id=_faker.pyint(min_value=100, max_value=200),
            product_name=product,
            expiry=timedelta(minutes=5),
        )

    tasks = await redis_task_store.list_tasks(owner=owner, user_id=user_id, product_name=product)
    assert {t.uuid for t in tasks} == {t.uuid for t in expected_tasks}


async def test_list_tasks_with_no_user_id(
    redis_task_store: RedisTaskStore,
):
    """Internal notifications have no user_id."""
    owner = "notifications-svc"
    product = "osparc"

    task_key = _faker.uuid4()
    await redis_task_store.create_task(
        task_key,
        TaskExecutionMetadata(name="send_notification"),
        owner=owner,
        user_id=None,
        product_name=product,
        expiry=timedelta(minutes=5),
    )

    # Query without user_id matches
    tasks = await redis_task_store.list_tasks(owner=owner, product_name=product)
    assert len(tasks) == 1
    assert tasks[0].uuid == UUID(task_key)

    # Query with a user_id does NOT match
    tasks = await redis_task_store.list_tasks(owner=owner, user_id=1, product_name=product)
    assert len(tasks) == 0


async def test_remove_task_cleans_up_zset_indexes(
    redis_task_store: RedisTaskStore,
):
    task_key = _faker.uuid4()

    await redis_task_store.create_task(
        task_key,
        TaskExecutionMetadata(name="my_task"),
        owner="test-svc",
        user_id=10003,
        product_name="osparc",
        expiry=timedelta(minutes=5),
    )
    assert len(await redis_task_store.list_tasks(owner="test-svc", user_id=10003, product_name="osparc")) == 1

    await redis_task_store.remove_task(task_key, owner="test-svc", user_id=10003, product_name="osparc")
    assert len(await redis_task_store.list_tasks(owner="test-svc", user_id=10003, product_name="osparc")) == 0


async def test_stale_zset_entries_are_pruned_on_list(
    redis_task_store: RedisTaskStore,
    redis_client_sdk: RedisClientSDK,
):
    task_key = _faker.uuid4()

    await redis_task_store.create_task(
        task_key,
        TaskExecutionMetadata(name="my_task"),
        owner="test-svc",
        user_id=10004,
        product_name="osparc",
        expiry=timedelta(minutes=5),
    )

    # Simulate hash expiry by deleting the hash directly (bypass remove_task)
    redis = redis_client_sdk.redis

    await redis.delete(_build_redis_task_or_group_key(task_key))

    # First list should return empty and prune the stale entry
    assert await redis_task_store.list_tasks(owner="test-svc", user_id=10004, product_name="osparc") == []
    # Second list confirms the ZSET is clean
    assert await redis_task_store.list_tasks(owner="test-svc", user_id=10004, product_name="osparc") == []


async def test_index_key_has_ttl_and_only_grows(
    redis_task_store: RedisTaskStore,
    redis_client_sdk: RedisClientSDK,
):
    """The ZSET index key must have a TTL bounded by the longest member expiry,
    so it cannot grow unboundedly when ``list_tasks`` is never called.
    """
    owner, user_id, product = "test-svc", 10005, "osparc"
    index_key = _build_redis_index_key_for_owner(owner, user_id, product)
    redis = redis_client_sdk.redis

    short_expiry = timedelta(minutes=1)
    long_expiry = timedelta(hours=1)

    # First add with a short expiry: index key gets a TTL ~ short_expiry
    await redis_task_store.create_task(
        _faker.uuid4(),
        TaskExecutionMetadata(name="my_task"),
        owner=owner,
        user_id=user_id,
        product_name=product,
        expiry=short_expiry,
    )
    ttl_after_short = await redis.ttl(index_key)
    assert 0 < ttl_after_short <= int(short_expiry.total_seconds())

    # Add a longer-lived task: TTL must be extended to cover it
    await redis_task_store.create_task(
        _faker.uuid4(),
        TaskExecutionMetadata(name="my_task"),
        owner=owner,
        user_id=user_id,
        product_name=product,
        expiry=long_expiry,
    )
    ttl_after_long = await redis.ttl(index_key)
    assert ttl_after_long >= int(long_expiry.total_seconds()) - 1

    # Add another short-lived task: TTL must NOT shrink below the long task's lifetime
    await redis_task_store.create_task(
        _faker.uuid4(),
        TaskExecutionMetadata(name="my_task"),
        owner=owner,
        user_id=user_id,
        product_name=product,
        expiry=short_expiry,
    )
    ttl_after_second_short = await redis.ttl(index_key)
    assert ttl_after_second_short >= int(long_expiry.total_seconds()) - 5
