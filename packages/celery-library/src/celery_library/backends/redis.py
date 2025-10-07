import contextlib
import logging
from dataclasses import dataclass
from datetime import timedelta
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

_CELERY_TASK_PREFIX: Final[str] = "celery-task-"
_CELERY_TASK_STREAM_PREFIX: Final[str] = "celery-task-stream-"
_CELERY_TASK_STREAM_EXPIRY_DEFAULT: Final[timedelta] = timedelta(minutes=5)
_CELERY_TASK_ID_KEY_ENCODING = "utf-8"
_CELERY_TASK_SCAN_COUNT_PER_BATCH: Final[int] = 1000
_CELERY_TASK_METADATA_KEY: Final[str] = "metadata"
_CELERY_TASK_PROGRESS_KEY: Final[str] = "progress"

_logger = logging.getLogger(__name__)


def _build_redis_task_key(task_key: TaskKey) -> str:
    return _CELERY_TASK_PREFIX + task_key


def _build_redis_stream_key(task_id: TaskKey) -> str:
    return _CELERY_TASK_STREAM_PREFIX + task_id


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
                key=_CELERY_TASK_METADATA_KEY,
                value=execution_metadata.model_dump_json(),
            )
        )
        await self._redis_client_sdk.redis.expire(
            redis_key,
            expiry,
        )

        if execution_metadata.streamed_result:
            stream_key = _build_redis_stream_key(task_key)
            await handle_redis_returns_union_types(
                self._redis_client_sdk.redis.rpush(stream_key, "__init__")
            )
            await handle_redis_returns_union_types(
                self._redis_client_sdk.redis.lpop(stream_key)
            )
            await handle_redis_returns_union_types(
                self._redis_client_sdk.redis.expire(
                    stream_key,
                    _CELERY_TASK_STREAM_EXPIRY_DEFAULT,
                )
            )

    async def get_task_metadata(self, task_key: TaskKey) -> ExecutionMetadata | None:
        raw_result = await handle_redis_returns_union_types(
            self._redis_client_sdk.redis.hget(
                _build_redis_task_key(task_key),
                _CELERY_TASK_METADATA_KEY,
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
        pipeline = self._redis_client_sdk.redis.pipeline()
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
            pipeline.hget(_key, _CELERY_TASK_METADATA_KEY)

        results = await pipeline.execute()

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
        await handle_redis_returns_union_types(
            self._redis_client_sdk.redis.rpush(
                stream_key,
                *[r.model_dump_json(by_alias=True) for r in result],
            )
        )

    async def pull_task_stream_items(
        self, task_key: TaskKey, limit: int = 20
    ) -> tuple[list[TaskStreamItem], int]:
        stream_key = _build_redis_stream_key(task_key)
        raw_items: list[str] = await handle_redis_returns_union_types(
            self._redis_client_sdk.redis.lrange(stream_key, 0, limit - 1)
        )

        stream_items = [TaskStreamItem.model_validate_json(item) for item in raw_items]

        if stream_items:
            await handle_redis_returns_union_types(
                self._redis_client_sdk.redis.ltrim(stream_key, len(stream_items), -1)
            )

        remaining = await handle_redis_returns_union_types(
            self._redis_client_sdk.redis.llen(stream_key)
        )

        return stream_items, remaining


if TYPE_CHECKING:
    _: type[TaskStore] = RedisTaskStore
