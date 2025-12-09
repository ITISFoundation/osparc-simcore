import contextlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final

from models_library.progress_bar import ProgressReport
from pydantic import ValidationError
from servicelib.celery.models import (
    WILDCARD,
    ExecutionMetadata,
    OwnerMetadata,
    Task,
    TaskKey,
    TaskStore,
    TaskStreamItem,
)
from servicelib.redis import RedisClientSDK, handle_redis_returns_union_types

_CELERY_TASK_DELIMTATOR: Final[str] = ":"

_CELERY_TASK_PREFIX: Final[str] = "celery-task-"
_CELERY_TASK_ID_KEY_ENCODING = "utf-8"
_CELERY_TASK_SCAN_COUNT_PER_BATCH: Final[int] = 1000
_CELERY_TASK_EXEC_METADATA_KEY: Final[str] = "exec-meta"
_CELERY_TASK_PROGRESS_KEY: Final[str] = "progress"

### Redis list to store streamed results
_CELERY_TASK_STREAM_PREFIX: Final[str] = "celery-task-stream-"
_CELERY_TASK_STREAM_EXPIRY: Final[timedelta] = timedelta(minutes=3)
_CELERY_TASK_STREAM_METADATA: Final[str] = "meta"
_CELERY_TASK_STREAM_DONE_KEY: Final[str] = "done"
_CELERY_TASK_STREAM_LAST_UPDATE_KEY: Final[str] = "last_update"

_logger = logging.getLogger(__name__)


def _build_redis_task_key(task_key: TaskKey) -> str:
    return f"{_CELERY_TASK_PREFIX}{task_key}"


def _build_redis_stream_key(task_key: TaskKey) -> str:
    return f"{_CELERY_TASK_STREAM_PREFIX}{task_key}"


def _build_redis_stream_meta_key(task_key: TaskKey) -> str:
    return f"{_build_redis_stream_key(task_key)}{_CELERY_TASK_DELIMTATOR}{_CELERY_TASK_STREAM_METADATA}"


@dataclass(frozen=True)
class RedisTaskStore:
    _redis_client_sdk: RedisClientSDK

    async def create_task(
        self,
        task_key: TaskKey,
        execution_metadata: ExecutionMetadata,
        expiry: timedelta,
    ) -> None:
        redis_key = _build_redis_task_key(task_key)
        await handle_redis_returns_union_types(
            self._redis_client_sdk.redis.hset(
                name=redis_key,
                key=_CELERY_TASK_EXEC_METADATA_KEY,
                value=execution_metadata.model_dump_json(),
            )
        )
        await self._redis_client_sdk.redis.expire(
            redis_key,
            expiry,
        )

    async def get_task_metadata(self, task_key: TaskKey) -> ExecutionMetadata | None:
        raw_result = await handle_redis_returns_union_types(
            self._redis_client_sdk.redis.hget(
                _build_redis_task_key(task_key),
                _CELERY_TASK_EXEC_METADATA_KEY,
            )
        )
        if not raw_result:
            return None

        try:
            return ExecutionMetadata.model_validate_json(raw_result)
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
                _build_redis_task_key(task_key),
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
        search_key = _CELERY_TASK_PREFIX + owner_metadata.model_dump_task_key(
            task_uuid=WILDCARD
        )

        keys: list[str] = []
        pipe = self._redis_client_sdk.redis.pipeline()
        async for key in self._redis_client_sdk.redis.scan_iter(
            match=search_key, count=_CELERY_TASK_SCAN_COUNT_PER_BATCH
        ):
            # fake redis (tests) returns bytes, real redis returns str
            _key = (
                key.decode(_CELERY_TASK_ID_KEY_ENCODING)
                if isinstance(key, bytes)
                else key
            )
            keys.append(_key)
            pipe.hget(_key, _CELERY_TASK_EXEC_METADATA_KEY)

        results = await pipe.execute()

        tasks = []
        for key, raw_metadata in zip(keys, results, strict=True):
            if raw_metadata is None:
                continue

            with contextlib.suppress(ValidationError):
                execution_metadata = ExecutionMetadata.model_validate_json(raw_metadata)
                tasks.append(
                    Task(
                        uuid=OwnerMetadata.get_task_uuid(key),
                        metadata=execution_metadata,
                    )
                )

        return tasks

    async def remove_task(self, task_key: TaskKey) -> None:
        await self._redis_client_sdk.redis.delete(
            _build_redis_task_key(task_key),
        )

    async def set_task_progress(
        self, task_key: TaskKey, report: ProgressReport
    ) -> None:
        await handle_redis_returns_union_types(
            self._redis_client_sdk.redis.hset(
                name=_build_redis_task_key(task_key),
                key=_CELERY_TASK_PROGRESS_KEY,
                value=report.model_dump_json(),
            )
        )

    async def task_exists(self, task_key: TaskKey) -> bool:
        n = await self._redis_client_sdk.redis.exists(
            _build_redis_task_key(task_key),
        )
        assert isinstance(n, int)  # nosec
        return n > 0

    async def push_task_stream_items(
        self, task_key: TaskKey, *result: TaskStreamItem
    ) -> None:
        stream_key = _build_redis_stream_key(task_key)
        stream_meta_key = _build_redis_stream_meta_key(task_key)

        pipe = self._redis_client_sdk.redis.pipeline()
        pipe.rpush(stream_key, *(r.model_dump_json(by_alias=True) for r in result))
        pipe.hset(
            stream_meta_key, mapping={"last_update": datetime.now(UTC).isoformat()}
        )
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
                value=datetime.now(UTC).isoformat(),
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

        stream_items = (
            [TaskStreamItem.model_validate_json(item) for item in raw_items]
            if raw_items
            else []
        )

        empty = (
            await handle_redis_returns_union_types(
                self._redis_client_sdk.redis.llen(stream_key)
            )
            == 0
        )

        return (
            stream_items,
            done == "1" and empty,
            datetime.fromisoformat(last_update) if last_update else None,
        )


if TYPE_CHECKING:
    _: type[TaskStore] = RedisTaskStore
