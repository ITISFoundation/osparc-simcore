import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Final

from models_library.progress_bar import ProgressReport
from pydantic import TypeAdapter, ValidationError
from servicelib.celery.models import (
    WILDCARD,
    ExecutionMetadata,
    OwnerMetadata,
    Task,
    TaskEvent,
    TaskEventID,
    TaskID,
    TaskInfoStore,
    TaskStatusEvent,
    TaskStatusValue,
)
from servicelib.redis import RedisClientSDK, handle_redis_returns_union_types

_CELERY_TASK_PREFIX: Final[str] = "celery-task-"
_CELERY_TASK_STREAM_PREFIX: Final[str] = "celery-task-stream-"
_CELERY_TASK_ID_KEY_ENCODING = "utf-8"
_CELERY_TASK_SCAN_COUNT_PER_BATCH: Final[int] = 1000
_CELERY_TASK_METADATA_KEY: Final[str] = "metadata"
_CELERY_TASK_PROGRESS_KEY: Final[str] = "progress"

_CELERY_TASK_STREAM_DEFAULT_ID: Final[str] = "0-0"
_CELERY_TASK_STREAM_BLOCK_TIMEOUT: Final[int] = 3 * 1000  # milliseconds
_CELERY_TASK_STREAM_COUNT: Final[int] = 10
_CELERY_TASK_STREAM_EXPIRE_DEFAULT: Final[timedelta] = timedelta(minutes=5)
_CELERY_TASK_STREAM_MAXLEN: Final[int] = 100_000


_logger = logging.getLogger(__name__)


def _build_key(task_id: TaskID) -> str:
    return _CELERY_TASK_PREFIX + task_id


def _build_stream_key(task_id: TaskID) -> str:
    return _CELERY_TASK_STREAM_PREFIX + task_id


@dataclass
class RedisTaskStore:
    _redis_client_sdk: RedisClientSDK

    async def create_task(
        self,
        task_id: TaskID,
        execution_metadata: ExecutionMetadata,
        expiry: timedelta,
    ) -> None:
        task_key = _build_key(task_id)
        await handle_redis_returns_union_types(
            self._redis_client_sdk.redis.hset(
                name=task_key,
                key=_CELERY_TASK_METADATA_KEY,
                value=execution_metadata.model_dump_json(),
            )
        )
        await self._redis_client_sdk.redis.expire(
            task_key,
            expiry,
        )

        if execution_metadata.streamed_result:
            stream_key = _build_stream_key(task_id)
            await self._redis_client_sdk.redis.xadd(
                stream_key,
                {
                    "event": TaskStatusEvent(
                        data=TaskStatusValue.CREATED
                    ).model_dump_json()
                },
                maxlen=_CELERY_TASK_STREAM_MAXLEN,
                approximate=True,
            )
            await self._redis_client_sdk.redis.expire(
                stream_key, _CELERY_TASK_STREAM_EXPIRE_DEFAULT
            )

    async def get_task_metadata(self, task_id: TaskID) -> ExecutionMetadata | None:
        raw_result = await handle_redis_returns_union_types(
            self._redis_client_sdk.redis.hget(
                _build_key(task_id), _CELERY_TASK_METADATA_KEY
            )
        )
        if not raw_result:
            return None

        try:
            return ExecutionMetadata.model_validate_json(raw_result)
        except ValidationError as exc:
            _logger.debug(
                "Failed to deserialize task metadata for task %s: %s", task_id, f"{exc}"
            )
            return None

    async def get_task_progress(self, task_id: TaskID) -> ProgressReport | None:
        raw_result = await handle_redis_returns_union_types(
            self._redis_client_sdk.redis.hget(
                _build_key(task_id), _CELERY_TASK_PROGRESS_KEY
            )
        )
        if not raw_result:
            return None

        try:
            return ProgressReport.model_validate_json(raw_result)
        except ValidationError as exc:
            _logger.debug(
                "Failed to deserialize task progress for task %s: %s", task_id, f"{exc}"
            )
            return None

    async def list_tasks(self, owner_metadata: OwnerMetadata) -> list[Task]:
        search_key = _CELERY_TASK_PREFIX + owner_metadata.model_dump_task_id(
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

    async def remove_task(self, task_id: TaskID) -> None:
        await self._redis_client_sdk.redis.delete(_build_key(task_id))
        await self._redis_client_sdk.redis.delete(_build_stream_key(task_id))

    async def set_task_progress(self, task_id: TaskID, report: ProgressReport) -> None:
        await handle_redis_returns_union_types(
            self._redis_client_sdk.redis.hset(
                name=_build_key(task_id),
                key=_CELERY_TASK_PROGRESS_KEY,
                value=report.model_dump_json(),
            )
        )

    async def task_exists(self, task_id: TaskID) -> bool:
        n = await self._redis_client_sdk.redis.exists(_build_key(task_id))
        assert isinstance(n, int)  # nosec
        return n > 0

    async def publish_task_event(self, task_id: TaskID, event: TaskEvent) -> None:
        stream_key = _build_stream_key(task_id)
        await self._redis_client_sdk.redis.xadd(
            stream_key,
            {"event": event.model_dump_json()},
        )

    async def consume_task_events(
        self, task_id: TaskID, last_id: str | None = None
    ) -> AsyncIterator[tuple[TaskEventID, TaskEvent]]:
        stream_key = _build_stream_key(task_id)
        while True:
            try:
                messages = await self._redis_client_sdk.redis.xread(
                    {stream_key: last_id or _CELERY_TASK_STREAM_DEFAULT_ID},
                    block=_CELERY_TASK_STREAM_BLOCK_TIMEOUT,
                    count=_CELERY_TASK_STREAM_COUNT,
                )
            except asyncio.CancelledError:
                _logger.debug("Task event consumption cancelled for task %s", task_id)
                break
            except Exception as exc:  # pylint: disable=broad-except
                _logger.warning(
                    "Redis error while consuming task events for task %s: %s. Stopping consumption.",
                    task_id,
                    exc,
                )
                break

            if not messages:
                continue
            for _, events in messages:
                for msg_id, data in events:
                    raw_event = data.get("event")
                    if raw_event is None:
                        continue

                    try:
                        event: TaskEvent = TypeAdapter(TaskEvent).validate_json(
                            raw_event
                        )
                        yield msg_id, event
                        last_id = msg_id
                    except ValidationError:
                        continue


if TYPE_CHECKING:
    _: type[TaskInfoStore] = RedisTaskStore
