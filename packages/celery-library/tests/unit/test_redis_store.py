# pylint: disable=redefined-outer-name

from collections.abc import AsyncIterator
from datetime import timedelta
from uuid import UUID

import pytest
from celery_library.backends import RedisTaskStore
from celery_library.backends._redis import (
    _build_redis_index_key_for_fields,
    _build_redis_task_or_group_key,
    _owner_fields_from_metadata,
)
from faker import Faker
from models_library.celery import (
    OwnerMetadata,
    TaskExecutionMetadata,
)
from servicelib.redis import RedisClientSDK
from settings_library.redis import RedisDatabase, RedisSettings

_faker = Faker()

pytest_simcore_core_services_selection = ["redis"]
pytest_simcore_ops_services_selection = []


class _TestOwnerMetadata(OwnerMetadata):
    user_id: int | None = None
    product_name: str | None = None


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
def redis_task_store(
    redis_client_sdk: RedisClientSDK,
) -> RedisTaskStore:
    return RedisTaskStore(redis_client_sdk)


async def test_list_tasks_uses_zset_index_not_scan(
    redis_task_store: RedisTaskStore,
    redis_client_sdk: RedisClientSDK,
    monkeypatch: pytest.MonkeyPatch,
):
    task_uuid = UUID(_faker.uuid4())
    owner_metadata = _TestOwnerMetadata(owner="test-svc", user_id=10001, product_name="osparc")
    task_key = owner_metadata.model_dump_key(task_or_group_uuid=task_uuid)

    await redis_task_store.create_task(
        task_key,
        TaskExecutionMetadata(name="my_task"),
        expiry=timedelta(minutes=5),
        owner_metadata=owner_metadata,
    )

    def _forbid_scan_iter(*_args: object, **_kwargs: object) -> None:
        msg = "list_tasks must not use redis.scan_iter"
        raise AssertionError(msg)

    monkeypatch.setattr(
        redis_client_sdk.redis,
        "scan_iter",
        _forbid_scan_iter,
    )

    tasks = await redis_task_store.list_tasks(owner_metadata)
    assert len(tasks) == 1
    assert tasks[0].uuid == task_uuid


async def test_list_tasks_filters_by_exact_owner_fields(
    redis_task_store: RedisTaskStore,
):
    owner = "test-svc"
    product = "osparc"
    user_id = 42
    expected_uuids: set[UUID] = set()

    # 5 tasks with same owner + product_name + user_id
    for _ in range(5):
        task_uuid = UUID(_faker.uuid4())
        om = _TestOwnerMetadata(owner=owner, user_id=user_id, product_name=product)
        task_key = om.model_dump_key(task_or_group_uuid=task_uuid)
        await redis_task_store.create_task(
            task_key,
            TaskExecutionMetadata(name="my_task"),
            expiry=timedelta(minutes=5),
            owner_metadata=om,
        )
        expected_uuids.add(task_uuid)

    # 3 tasks with a different user id
    for _ in range(3):
        task_uuid = UUID(_faker.uuid4())
        om = _TestOwnerMetadata(
            owner=owner,
            user_id=_faker.pyint(min_value=100, max_value=200),
            product_name=product,
        )
        task_key = om.model_dump_key(task_or_group_uuid=task_uuid)
        await redis_task_store.create_task(
            task_key,
            TaskExecutionMetadata(name="my_task"),
            expiry=timedelta(minutes=5),
            owner_metadata=om,
        )

    query_om = _TestOwnerMetadata(owner=owner, user_id=user_id, product_name=product)
    tasks = await redis_task_store.list_tasks(query_om)
    assert {t.uuid for t in tasks} == expected_uuids


async def test_list_tasks_with_no_user_id(
    redis_task_store: RedisTaskStore,
):
    """Internal notifications have no user_id."""
    owner = "notifications-svc"
    product = "osparc"
    task_uuid = UUID(_faker.uuid4())

    om = _TestOwnerMetadata(owner=owner, user_id=None, product_name=product)
    task_key = om.model_dump_key(task_or_group_uuid=task_uuid)
    await redis_task_store.create_task(
        task_key,
        TaskExecutionMetadata(name="send_notification"),
        expiry=timedelta(minutes=5),
        owner_metadata=om,
    )

    # Query without user_id matches
    query_no_uid = _TestOwnerMetadata(owner=owner, product_name=product)
    tasks = await redis_task_store.list_tasks(query_no_uid)
    assert len(tasks) == 1
    assert tasks[0].uuid == task_uuid

    # Query with a user_id does NOT match
    query_with_uid = _TestOwnerMetadata(owner=owner, user_id=1, product_name=product)
    tasks = await redis_task_store.list_tasks(query_with_uid)
    assert len(tasks) == 0


async def test_remove_task_cleans_up_zset_indexes(
    redis_task_store: RedisTaskStore,
):
    task_uuid = UUID(_faker.uuid4())
    om = _TestOwnerMetadata(owner="test-svc", user_id=10003, product_name="osparc")
    task_key = om.model_dump_key(task_or_group_uuid=task_uuid)

    await redis_task_store.create_task(
        task_key,
        TaskExecutionMetadata(name="my_task"),
        expiry=timedelta(minutes=5),
        owner_metadata=om,
    )
    assert len(await redis_task_store.list_tasks(om)) == 1

    await redis_task_store.remove_task(task_key, owner_metadata=om)
    assert len(await redis_task_store.list_tasks(om)) == 0


async def test_stale_zset_entries_are_pruned_on_list(
    redis_task_store: RedisTaskStore,
    redis_client_sdk: RedisClientSDK,
):
    task_uuid = UUID(_faker.uuid4())
    om = _TestOwnerMetadata(owner="test-svc", user_id=10004, product_name="osparc")
    task_key = om.model_dump_key(task_or_group_uuid=task_uuid)

    await redis_task_store.create_task(
        task_key,
        TaskExecutionMetadata(name="my_task"),
        expiry=timedelta(minutes=5),
        owner_metadata=om,
    )

    # Simulate hash expiry by deleting the hash directly (bypass remove_task)
    await redis_client_sdk.redis.delete(_build_redis_task_or_group_key(task_key))

    # First list should return empty and prune the stale entry
    assert await redis_task_store.list_tasks(om) == []
    # Second list confirms the ZSET is clean
    assert await redis_task_store.list_tasks(om) == []


async def test_index_key_has_ttl_and_only_grows(
    redis_task_store: RedisTaskStore,
    redis_client_sdk: RedisClientSDK,
):
    """The ZSET index key must have a TTL bounded by the longest member expiry."""
    om = _TestOwnerMetadata(owner="test-svc", user_id=10005, product_name="osparc")
    owner, extras = _owner_fields_from_metadata(om)
    index_key = _build_redis_index_key_for_fields(owner, extras)
    redis = redis_client_sdk.redis

    short_expiry = timedelta(minutes=1)
    long_expiry = timedelta(hours=1)

    # First add with a short expiry
    task_key = om.model_dump_key(task_or_group_uuid=UUID(_faker.uuid4()))
    await redis_task_store.create_task(
        task_key,
        TaskExecutionMetadata(name="my_task"),
        expiry=short_expiry,
        owner_metadata=om,
    )
    ttl_after_short = await redis.ttl(index_key)
    assert 0 < ttl_after_short <= int(short_expiry.total_seconds())

    # Add a longer-lived task: TTL must be extended
    task_key = om.model_dump_key(task_or_group_uuid=UUID(_faker.uuid4()))
    await redis_task_store.create_task(
        task_key,
        TaskExecutionMetadata(name="my_task"),
        expiry=long_expiry,
        owner_metadata=om,
    )
    ttl_after_long = await redis.ttl(index_key)
    assert ttl_after_long >= int(long_expiry.total_seconds()) - 1

    # Add another short-lived task: TTL must NOT shrink
    task_key = om.model_dump_key(task_or_group_uuid=UUID(_faker.uuid4()))
    await redis_task_store.create_task(
        task_key,
        TaskExecutionMetadata(name="my_task"),
        expiry=short_expiry,
        owner_metadata=om,
    )
    ttl_after_second_short = await redis.ttl(index_key)
    assert ttl_after_second_short >= int(long_expiry.total_seconds()) - 5


async def test_create_task_with_index_false_skips_owner_index(
    redis_task_store: RedisTaskStore,
    redis_client_sdk: RedisClientSDK,
):
    """Group sub-tasks must not appear in the owner index."""
    om = _TestOwnerMetadata(owner="test-svc", user_id=10006, product_name="osparc")
    indexed_uuid = UUID(_faker.uuid4())
    sub_task_uuid = UUID(_faker.uuid4())

    indexed_key = om.model_dump_key(task_or_group_uuid=indexed_uuid)
    sub_task_key = om.model_dump_key(task_or_group_uuid=sub_task_uuid)

    await redis_task_store.create_task(
        indexed_key,
        TaskExecutionMetadata(name="my_task"),
        expiry=timedelta(minutes=5),
        owner_metadata=om,
    )
    await redis_task_store.create_task(
        sub_task_key,
        TaskExecutionMetadata(name="my_sub_task"),
        expiry=timedelta(minutes=5),
        owner_metadata=om,
        index=False,
    )

    # Sub-task hash exists
    assert await redis_client_sdk.redis.exists(_build_redis_task_or_group_key(sub_task_key)) == 1
    # Only the indexed task appears in listing
    listed = await redis_task_store.list_tasks(om)
    assert {t.uuid for t in listed} == {indexed_uuid}
