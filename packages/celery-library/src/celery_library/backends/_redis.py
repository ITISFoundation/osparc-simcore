import contextlib
import itertools
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final

from models_library.celery import (
    ExecutionMetadata,
    ExecutorType,
    GroupExecutionMetadata,
    Task,
    TaskExecutionMetadata,
    TaskID,
    TaskStore,
    TaskStreamItem,
)
from models_library.progress_bar import ProgressReport
from pydantic import TypeAdapter, ValidationError
from servicelib.redis import RedisClientSDK, handle_redis_returns_union_types

_CELERY_TASK_DELIMTATOR: Final[str] = ":"

_CELERY_TASK_PREFIX: Final[str] = "celery-task-"
_CELERY_TASK_ID_KEY_ENCODING: Final[str] = "utf-8"
_CELERY_TASK_EXEC_METADATA_KEY: Final[str] = "exec-meta"
_CELERY_TASK_PROGRESS_KEY: Final[str] = "progress"
_CELERY_TASK_INDEX_PREFIX: Final[str] = "celery-task-index-"

_TASK_ID_ADAPTER: Final[TypeAdapter[TaskID]] = TypeAdapter(TaskID)

# Redis list to store streamed results
_CELERY_TASK_STREAM_PREFIX: Final[str] = "celery-task-stream-"
_CELERY_TASK_STREAM_EXPIRY: Final[timedelta] = timedelta(minutes=3)
_CELERY_TASK_STREAM_METADATA: Final[str] = "meta"
_CELERY_TASK_STREAM_DONE_KEY: Final[str] = "done"
_CELERY_TASK_STREAM_LAST_UPDATE_KEY: Final[str] = "last_update"

_logger = logging.getLogger(__name__)


# --- key builders ---


def _build_redis_task_key(task_id: TaskID) -> str:
    return f"{_CELERY_TASK_PREFIX}{task_id}"


def _build_redis_stream_key(task_id: TaskID) -> str:
    return f"{_CELERY_TASK_STREAM_PREFIX}{task_id}"


def _build_redis_stream_meta_key(task_id: TaskID) -> str:
    return f"{_build_redis_stream_key(task_id)}{_CELERY_TASK_DELIMTATOR}{_CELERY_TASK_STREAM_METADATA}"


def _build_redis_index_key(suffix: str) -> str:
    return f"{_CELERY_TASK_INDEX_PREFIX}{suffix}"


def _concrete_owner_fields(
    owner: str,
    user_id: int | None,
    product_name: str | None,
) -> list[tuple[str, str | int]]:
    """Return (field_name, value) pairs for non-None owner fields, sorted by name."""
    pairs: list[tuple[str, str | int]] = [("owner", owner)]
    if user_id is not None:
        pairs.append(("user_id", user_id))
    if product_name is not None:
        pairs.append(("product_name", product_name))
    return sorted(pairs)


def _build_redis_index_key_for_owner(
    owner: str,
    user_id: int | None,
    product_name: str | None,
) -> str:
    """Build a single sorted-set index key from the supplied owner fields.

    Used for querying — the same key is produced at creation time for the
    matching subset of fields, so a query with a partial set of fields
    (``None`` acting as a wildcard) hits a dedicated secondary index.
    """
    parts = [f"{k}={v}" for k, v in _concrete_owner_fields(owner, user_id, product_name)]
    return _build_redis_index_key(_CELERY_TASK_DELIMTATOR.join(parts))


def _iter_redis_index_keys_for_owner(
    owner: str,
    user_id: int | None,
    product_name: str | None,
) -> Iterator[str]:
    """Yield one index key per subset of the concrete owner fields.

    ``owner`` is always part of every subset; the optional fields
    (``user_id``, ``product_name``) are independently included or omitted,
    so a task with all fields set is added to ``2 ** k`` secondary indexes
    (where ``k`` is the number of non-``None`` optional fields). This lets
    ``list_tasks`` answer queries with any partial combination of owner
    fields in ``O(log N)`` against a single sorted set.
    """
    optional: list[tuple[str, str | int | None]] = [
        ("user_id", user_id),
        ("product_name", product_name),
    ]
    concrete_optional = [(name, value) for name, value in optional if value is not None]
    for size in range(len(concrete_optional) + 1):
        for combo in itertools.combinations(concrete_optional, size):
            kwargs: dict[str, str | int | None] = {"user_id": None, "product_name": None}
            kwargs.update(dict(combo))
            yield _build_redis_index_key_for_owner(owner, **kwargs)  # type: ignore[arg-type]


@dataclass(frozen=True)
class RedisTaskStore:
    _redis_client_sdk: RedisClientSDK

    async def _refresh_index_key_ttl(self, index_key: str, expiry: timedelta) -> None:
        """Ensure the index key TTL is at least ``expiry``.

        ``EXPIRE ... GT`` cannot be used because Redis treats a key with no TTL
        as having infinite TTL for the purpose of the GT comparison, so it would
        leave the index key persistent on first creation. We instead read the
        current TTL and only extend it.
        """
        current_ttl = await self._redis_client_sdk.redis.ttl(index_key)
        # ttl returns: -2 (no key), -1 (no TTL), or remaining seconds.
        if current_ttl < int(expiry.total_seconds()):
            await self._redis_client_sdk.redis.expire(index_key, expiry)

    async def create_group(
        self,
        group_uuid: TaskID,
        execution_metadata: GroupExecutionMetadata,
        task_uuids: list[TaskID],
        *,
        owner: str,
        user_id: int | None = None,
        product_name: str | None = None,
        expiry: timedelta,
    ) -> None:
        redis_group_key = _build_redis_task_key(group_uuid)
        pipe = self._redis_client_sdk.redis.pipeline()
        index_score = datetime.now(tz=UTC).timestamp()

        pipe.hset(
            name=redis_group_key,
            key=_CELERY_TASK_EXEC_METADATA_KEY,
            value=execution_metadata.model_dump_json(),
        )
        index_keys = list(_iter_redis_index_keys_for_owner(owner, user_id, product_name))
        for index_key in index_keys:
            pipe.zadd(index_key, {f"{group_uuid}": index_score})

        # Sub-task hashes are stored so they can be looked up by UUID, but they
        # are intentionally NOT added to the owner index: the parent group is
        # the listable unit. ``create_task`` is called with ``index=False`` for
        # each sub-task in ``TaskManager.submit_group``.
        for task_uuid, (task_execution_metadata, _) in zip(task_uuids, execution_metadata.tasks, strict=True):
            pipe.hset(
                name=_build_redis_task_key(task_uuid),
                key=_CELERY_TASK_EXEC_METADATA_KEY,
                value=task_execution_metadata.model_dump_json(),
            )
        await pipe.execute()
        await self._redis_client_sdk.redis.expire(
            redis_group_key,
            expiry,
        )
        for index_key in index_keys:
            await self._refresh_index_key_ttl(index_key, expiry)

    async def create_task(
        self,
        task_uuid: TaskID,
        execution_metadata: TaskExecutionMetadata,
        *,
        owner: str,
        user_id: int | None = None,
        product_name: str | None = None,
        expiry: timedelta,
        index: bool = True,
    ) -> None:
        redis_key = _build_redis_task_key(task_uuid)
        index_score = datetime.now(tz=UTC).timestamp()

        pipe = self._redis_client_sdk.redis.pipeline()
        pipe.hset(
            name=redis_key,
            key=_CELERY_TASK_EXEC_METADATA_KEY,
            value=execution_metadata.model_dump_json(),
        )
        index_keys: list[str] = []
        if index:
            index_keys = list(_iter_redis_index_keys_for_owner(owner, user_id, product_name))
            for index_key in index_keys:
                pipe.zadd(index_key, {f"{task_uuid}": index_score})
        await pipe.execute()

        await self._redis_client_sdk.redis.expire(
            redis_key,
            expiry,
        )
        for index_key in index_keys:
            await self._refresh_index_key_ttl(index_key, expiry)

    async def get_task_metadata(self, task_uuid: TaskID) -> ExecutionMetadata | None:
        redis_key = _build_redis_task_key(task_uuid)
        raw_result = await handle_redis_returns_union_types(
            self._redis_client_sdk.redis.hget(
                name=redis_key,
                key=_CELERY_TASK_EXEC_METADATA_KEY,
            )
        )
        if not raw_result:
            return None

        try:
            return TypeAdapter(ExecutionMetadata).validate_json(raw_result)
        except ValidationError as exc:
            _logger.debug(
                "Failed to deserialize task metadata for task %s: %s",
                task_uuid,
                f"{exc}",
            )
            return None

    async def get_task_progress(self, task_uuid: TaskID) -> ProgressReport | None:
        raw_result = await handle_redis_returns_union_types(
            self._redis_client_sdk.redis.hget(
                _build_redis_task_key(task_uuid),
                _CELERY_TASK_PROGRESS_KEY,
            )
        )
        if not raw_result:
            return None

        try:
            return ProgressReport.model_validate_json(raw_result)
        except ValidationError as exc:
            _logger.debug(
                "Failed to deserialize task progress for task %s: %s",
                task_uuid,
                f"{exc}",
            )
            return None

    async def list_tasks(
        self,
        *,
        owner: str,
        user_id: int | None = None,
        product_name: str | None = None,
    ) -> list[Task]:
        owner_index_key = _build_redis_index_key_for_owner(owner, user_id, product_name)

        raw_members = await self._redis_client_sdk.redis.zrange(owner_index_key, 0, -1)
        if not raw_members:
            return []

        members = [m.decode(_CELERY_TASK_ID_KEY_ENCODING) if isinstance(m, bytes) else m for m in raw_members]

        pipe = self._redis_client_sdk.redis.pipeline()
        member_uuids: list[TaskID] = []
        for member in members:
            member_uuid = _TASK_ID_ADAPTER.validate_python(member)
            member_uuids.append(member_uuid)
            pipe.hget(_build_redis_task_key(member_uuid), _CELERY_TASK_EXEC_METADATA_KEY)

        results = await pipe.execute()

        tasks = []
        stale_members: list[str] = []
        for member, member_uuid, raw_metadata in zip(members, member_uuids, results, strict=True):
            if raw_metadata is None:
                stale_members.append(member)
                continue

            with contextlib.suppress(ValidationError):
                execution_metadata: ExecutionMetadata = TypeAdapter(ExecutionMetadata).validate_json(raw_metadata)
                if execution_metadata.type == ExecutorType.GROUP_TASK:
                    continue

                tasks.append(
                    Task(
                        uuid=member_uuid,
                        metadata=execution_metadata,
                    )
                )

        if stale_members:
            await self._redis_client_sdk.redis.zrem(owner_index_key, *stale_members)

        return tasks

    async def remove_task(
        self,
        task_uuid: TaskID,
        *,
        owner: str,
        user_id: int | None = None,
        product_name: str | None = None,
    ) -> None:
        pipe = self._redis_client_sdk.redis.pipeline()
        pipe.delete(_build_redis_task_key(task_uuid))
        for index_key in _iter_redis_index_keys_for_owner(owner, user_id, product_name):
            pipe.zrem(index_key, f"{task_uuid}")
        await pipe.execute()

    async def remove_task_hash(self, task_id: TaskID) -> None:
        await self._redis_client_sdk.redis.delete(_build_redis_task_key(task_id))

    async def set_task_progress(self, task_uuid: TaskID, report: ProgressReport) -> None:
        await handle_redis_returns_union_types(
            self._redis_client_sdk.redis.hset(
                name=_build_redis_task_key(task_uuid),
                key=_CELERY_TASK_PROGRESS_KEY,
                value=report.model_dump_json(),
            )
        )

    async def task_exists(self, task_id: TaskID) -> bool:
        n = await self._redis_client_sdk.redis.exists(
            _build_redis_task_key(task_id),
        )
        assert isinstance(n, int)  # nosec
        return n > 0

    async def push_task_stream_items(self, task_uuid: TaskID, *result: TaskStreamItem) -> None:
        stream_key = _build_redis_stream_key(task_uuid)
        stream_meta_key = _build_redis_stream_meta_key(task_uuid)

        pipe = self._redis_client_sdk.redis.pipeline()
        pipe.rpush(stream_key, *(r.model_dump_json(by_alias=True) for r in result))
        pipe.hset(stream_meta_key, mapping={"last_update": datetime.now(tz=UTC).isoformat()})
        pipe.expire(stream_key, _CELERY_TASK_STREAM_EXPIRY)
        pipe.expire(stream_meta_key, _CELERY_TASK_STREAM_EXPIRY)
        await pipe.execute()

    async def set_task_stream_done(self, task_uuid: TaskID) -> None:
        stream_meta_key = _build_redis_stream_meta_key(task_uuid)
        await handle_redis_returns_union_types(
            self._redis_client_sdk.redis.hset(
                name=stream_meta_key,
                key=_CELERY_TASK_STREAM_DONE_KEY,
                value="1",
            )
        )

    async def set_task_stream_last_update(self, task_uuid: TaskID) -> None:
        stream_meta_key = _build_redis_stream_meta_key(task_uuid)
        await handle_redis_returns_union_types(
            self._redis_client_sdk.redis.hset(
                name=stream_meta_key,
                key=_CELERY_TASK_STREAM_LAST_UPDATE_KEY,
                value=datetime.now(tz=UTC).isoformat(),
            )
        )

    async def pull_task_stream_items(
        self, task_uuid: TaskID, limit: int = 20
    ) -> tuple[list[TaskStreamItem], bool, datetime | None]:
        stream_key = _build_redis_stream_key(task_uuid)
        meta_key = _build_redis_stream_meta_key(task_uuid)

        async with self._redis_client_sdk.redis.pipeline(transaction=True) as pipe:
            pipe.lpop(stream_key, limit)
            pipe.hget(meta_key, _CELERY_TASK_STREAM_DONE_KEY)
            pipe.hget(meta_key, _CELERY_TASK_STREAM_LAST_UPDATE_KEY)
            raw_items, done, last_update = await pipe.execute()

        stream_items = [TaskStreamItem.model_validate_json(item) for item in raw_items] if raw_items else []

        empty = await handle_redis_returns_union_types(self._redis_client_sdk.redis.llen(stream_key)) == 0

        return (
            stream_items,
            done == "1" and empty,
            datetime.fromisoformat(last_update) if last_update else None,
        )


if TYPE_CHECKING:
    _: type[TaskStore] = RedisTaskStore
