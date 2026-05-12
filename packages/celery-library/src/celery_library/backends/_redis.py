import contextlib
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final

from models_library.celery import (
    WILDCARD,
    ExecutionMetadata,
    ExecutorType,
    GroupExecutionMetadata,
    GroupKey,
    OwnerMetadata,
    Task,
    TaskExecutionMetadata,
    TaskKey,
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

# Redis list to store streamed results
_CELERY_TASK_STREAM_PREFIX: Final[str] = "celery-task-stream-"
_CELERY_TASK_STREAM_EXPIRY: Final[timedelta] = timedelta(minutes=3)
_CELERY_TASK_STREAM_METADATA: Final[str] = "meta"
_CELERY_TASK_STREAM_DONE_KEY: Final[str] = "done"
_CELERY_TASK_STREAM_LAST_UPDATE_KEY: Final[str] = "last_update"

_logger = logging.getLogger(__name__)


# --- key builders ---


def _build_redis_task_or_group_key(key: TaskKey | GroupKey) -> str:
    return f"{_CELERY_TASK_PREFIX}{key}"


def _build_redis_stream_key(task_key: TaskKey) -> str:
    return f"{_CELERY_TASK_STREAM_PREFIX}{task_key}"


def _build_redis_stream_meta_key(task_key: TaskKey) -> str:
    return f"{_build_redis_stream_key(task_key)}{_CELERY_TASK_DELIMTATOR}{_CELERY_TASK_STREAM_METADATA}"


# --- secondary index helpers ---


def _build_redis_index_key(suffix: str) -> str:
    return f"{_CELERY_TASK_INDEX_PREFIX}{suffix}"


def _owner_fields_from_metadata(
    owner_metadata: OwnerMetadata,
) -> tuple[str, dict[str, str | int]]:
    """Extract the owner field and optional extra fields from OwnerMetadata.

    Returns (owner, {field_name: value}) for non-None extra fields.
    """
    data = owner_metadata.model_dump(mode="json")
    owner: str = data.pop("owner")
    # only keep non-None and non-wildcard optional fields
    extras = {k: v for k, v in sorted(data.items()) if v is not None and v != WILDCARD}
    return owner, extras


def _build_redis_index_key_for_fields(
    owner: str,
    extras: dict[str, str | int],
) -> str:
    """Build a single sorted-set index key from owner + selected extra fields."""
    parts = [f"owner={owner}"]
    for k, v in sorted(extras.items()):
        parts.append(f"{k}={v}")
    return _build_redis_index_key(_CELERY_TASK_DELIMTATOR.join(parts))


def _iter_redis_index_keys(
    owner: str,
    extras: dict[str, str | int],
    additional_subsets: list[frozenset[str]] | None = None,
) -> Iterator[str]:
    """Yield index keys for a task/group.

    Always yields the full-field index key (owner + all extras).  If
    *additional_subsets* is provided, also yields keys for those field
    subsets so that partial-field queries are supported.

    ``additional_subsets`` should come from
    :meth:`OwnerMetadata.indexed_field_subsets`.
    """
    # Always index the full key
    yield _build_redis_index_key_for_fields(owner, extras)

    if additional_subsets is not None:
        full_fields = frozenset(extras.keys())
        for subset in additional_subsets:
            if subset != full_fields:
                partial = {k: v for k, v in sorted(extras.items()) if k in subset}
                yield _build_redis_index_key_for_fields(owner, partial)


@dataclass(frozen=True)
class RedisTaskStore:
    _redis_client_sdk: RedisClientSDK

    async def _refresh_index_key_ttl(self, index_key: str, expiry: timedelta) -> None:
        """Ensure the index key TTL is at least ``expiry``.

        We read the current TTL and only extend it to avoid overwriting a
        longer TTL set by a concurrent call.
        """
        current_ttl = await self._redis_client_sdk.redis.ttl(index_key)
        if current_ttl < int(expiry.total_seconds()):
            await self._redis_client_sdk.redis.expire(index_key, expiry)

    def _add_to_indexes(
        self,
        pipe,
        task_or_group_key: TaskKey | GroupKey,
        owner_metadata: OwnerMetadata | None,
    ) -> list[str]:
        """Add a task/group key to all relevant ZSET secondary indexes.

        Returns the list of index keys that were written (needed for TTL refresh).
        """
        if owner_metadata is None:
            return []
        owner, extras = _owner_fields_from_metadata(owner_metadata)
        additional_subsets = type(owner_metadata).indexed_field_subsets()
        index_keys = list(_iter_redis_index_keys(owner, extras, additional_subsets))
        index_score = datetime.now(tz=UTC).timestamp()
        for index_key in index_keys:
            pipe.zadd(index_key, {task_or_group_key: index_score})
        return index_keys

    async def _set_index_ttls(self, index_keys: list[str], expiry: timedelta) -> None:
        for index_key in index_keys:
            await self._refresh_index_key_ttl(index_key, expiry)

    async def create_group(
        self,
        group_key: GroupKey,
        execution_metadata: GroupExecutionMetadata,
        task_keys: list[TaskKey],
        expiry: timedelta,
        owner_metadata: OwnerMetadata | None = None,
    ) -> None:
        redis_group_key = _build_redis_task_or_group_key(group_key)
        pipe = self._redis_client_sdk.redis.pipeline()
        pipe.hset(
            name=redis_group_key,
            key=_CELERY_TASK_EXEC_METADATA_KEY,
            value=execution_metadata.model_dump_json(),
        )

        index_keys = self._add_to_indexes(pipe, group_key, owner_metadata)

        # Sub-task hashes — NOT added to index (parent group is the listable unit)
        for task_key, (task_execution_metadata, _) in zip(task_keys, execution_metadata.tasks, strict=True):
            pipe.hset(
                name=_build_redis_task_or_group_key(task_key),
                key=_CELERY_TASK_EXEC_METADATA_KEY,
                value=task_execution_metadata.model_dump_json(),
            )
        await pipe.execute()
        await self._redis_client_sdk.redis.expire(redis_group_key, expiry)
        await self._set_index_ttls(index_keys, expiry)

    async def create_task(
        self,
        task_key: TaskKey,
        execution_metadata: TaskExecutionMetadata,
        expiry: timedelta,
        owner_metadata: OwnerMetadata | None = None,
    ) -> None:
        redis_key = _build_redis_task_or_group_key(task_key)

        pipe = self._redis_client_sdk.redis.pipeline()
        pipe.hset(
            name=redis_key,
            key=_CELERY_TASK_EXEC_METADATA_KEY,
            value=execution_metadata.model_dump_json(),
        )

        index_keys = self._add_to_indexes(pipe, task_key, owner_metadata)
        await pipe.execute()

        await self._redis_client_sdk.redis.expire(redis_key, expiry)
        await self._set_index_ttls(index_keys, expiry)

    async def get_task_metadata(self, task_key: TaskKey) -> ExecutionMetadata | None:
        raw_result = await handle_redis_returns_union_types(
            self._redis_client_sdk.redis.hget(
                _build_redis_task_or_group_key(task_key),
                _CELERY_TASK_EXEC_METADATA_KEY,
            )
        )
        if not raw_result:
            return None

        try:
            return TypeAdapter(ExecutionMetadata).validate_json(raw_result)
        except ValidationError as exc:
            _logger.debug(
                "Failed to deserialize task metadata for task %s: %s",
                task_key,
                f"{exc}",
            )
            return None

    async def get_task_progress(self, task_key: TaskKey) -> ProgressReport | None:
        raw_result = await handle_redis_returns_union_types(
            self._redis_client_sdk.redis.hget(
                _build_redis_task_or_group_key(task_key),
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
                task_key,
                f"{exc}",
            )
            return None

    async def list_tasks(self, owner_metadata: OwnerMetadata) -> list[Task]:
        owner, extras = _owner_fields_from_metadata(owner_metadata)
        owner_index_key = _build_redis_index_key_for_fields(owner, extras)

        raw_members = await self._redis_client_sdk.redis.zrange(owner_index_key, 0, -1)
        if not raw_members:
            return []

        # Members are full task/group keys
        members = [m.decode(_CELERY_TASK_ID_KEY_ENCODING) if isinstance(m, bytes) else m for m in raw_members]

        pipe = self._redis_client_sdk.redis.pipeline()
        for task_key in members:
            pipe.hget(_build_redis_task_or_group_key(task_key), _CELERY_TASK_EXEC_METADATA_KEY)

        results = await pipe.execute()

        tasks = []
        stale_members: list[str] = []
        for task_key, raw_metadata in zip(members, results, strict=True):
            if raw_metadata is None:
                stale_members.append(task_key)
                continue

            with contextlib.suppress(ValidationError):
                execution_metadata: ExecutionMetadata = TypeAdapter(ExecutionMetadata).validate_json(raw_metadata)
                if execution_metadata.type == ExecutorType.GROUP_TASK:
                    continue

                tasks.append(
                    Task(
                        uuid=OwnerMetadata.get_task_or_group_uuid(task_key),
                        metadata=execution_metadata,
                    )
                )

        # Lazily clean stale index entries
        if stale_members:
            await self._redis_client_sdk.redis.zrem(owner_index_key, *stale_members)

        return tasks

    async def remove_task(self, task_key: TaskKey, owner_metadata: OwnerMetadata | None = None) -> None:
        pipe = self._redis_client_sdk.redis.pipeline()
        pipe.delete(_build_redis_task_or_group_key(task_key))

        if owner_metadata is not None:
            owner, extras = _owner_fields_from_metadata(owner_metadata)
            additional_subsets = type(owner_metadata).indexed_field_subsets()
            for index_key in _iter_redis_index_keys(owner, extras, additional_subsets):
                pipe.zrem(index_key, task_key)

        await pipe.execute()

    async def set_task_progress(self, task_key: TaskKey, report: ProgressReport) -> None:
        await handle_redis_returns_union_types(
            self._redis_client_sdk.redis.hset(
                name=_build_redis_task_or_group_key(task_key),
                key=_CELERY_TASK_PROGRESS_KEY,
                value=report.model_dump_json(),
            )
        )

    async def task_or_group_exists(self, task_or_group_key: TaskKey | GroupKey) -> bool:
        n = await self._redis_client_sdk.redis.exists(
            _build_redis_task_or_group_key(task_or_group_key),
        )
        assert isinstance(n, int)  # nosec
        return n > 0

    async def push_task_stream_items(self, task_key: TaskKey, *result: TaskStreamItem) -> None:
        stream_key = _build_redis_stream_key(task_key)
        stream_meta_key = _build_redis_stream_meta_key(task_key)

        pipe = self._redis_client_sdk.redis.pipeline()
        pipe.rpush(stream_key, *(r.model_dump_json(by_alias=True) for r in result))
        pipe.hset(stream_meta_key, mapping={"last_update": datetime.now(tz=UTC).isoformat()})
        pipe.expire(stream_key, _CELERY_TASK_STREAM_EXPIRY)
        pipe.expire(stream_meta_key, _CELERY_TASK_STREAM_EXPIRY)
        await pipe.execute()

    async def set_task_stream_done(self, task_key: TaskKey) -> None:
        stream_meta_key = _build_redis_stream_meta_key(task_key)
        await handle_redis_returns_union_types(
            self._redis_client_sdk.redis.hset(
                name=stream_meta_key,
                key=_CELERY_TASK_STREAM_DONE_KEY,
                value="1",
            )
        )

    async def set_task_stream_last_update(self, task_key: TaskKey) -> None:
        stream_meta_key = _build_redis_stream_meta_key(task_key)
        await handle_redis_returns_union_types(
            self._redis_client_sdk.redis.hset(
                name=stream_meta_key,
                key=_CELERY_TASK_STREAM_LAST_UPDATE_KEY,
                value=datetime.now(tz=UTC).isoformat(),
            )
        )

    async def pull_task_stream_items(
        self, task_key: TaskKey, limit: int = 20
    ) -> tuple[list[TaskStreamItem], bool, datetime | None]:
        stream_key = _build_redis_stream_key(task_key)
        meta_key = _build_redis_stream_meta_key(task_key)

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
