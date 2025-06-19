import contextlib
import logging
from datetime import timedelta
from typing import Final

from models_library.progress_bar import ProgressReport
from pydantic import ValidationError
from servicelib.queued_tasks.models import (
    Task,
    TaskContext,
    TaskID,
    TaskMetadata,
    TaskUUID,
)
from servicelib.redis import RedisClientSDK

from ..utils import build_task_id_prefix

_CELERY_TASK_INFO_PREFIX: Final[str] = "celery-task-info-"
_CELERY_TASK_ID_KEY_ENCODING = "utf-8"
_CELERY_TASK_ID_KEY_SEPARATOR: Final[str] = ":"
_CELERY_TASK_SCAN_COUNT_PER_BATCH: Final[int] = 10000
_CELERY_TASK_METADATA_KEY: Final[str] = "metadata"
_CELERY_TASK_PROGRESS_KEY: Final[str] = "progress"

_logger = logging.getLogger(__name__)


def _build_key(task_id: TaskID) -> str:
    return _CELERY_TASK_INFO_PREFIX + task_id


class RedisTaskInfoStore:
    def __init__(self, redis_client_sdk: RedisClientSDK) -> None:
        self._redis_client_sdk = redis_client_sdk

    async def create_task(
        self,
        task_id: TaskID,
        task_metadata: TaskMetadata,
        expiry: timedelta,
    ) -> None:
        task_key = _build_key(task_id)
        await self._redis_client_sdk.redis.hset(
            name=task_key,
            key=_CELERY_TASK_METADATA_KEY,
            value=task_metadata.model_dump_json(),
        )  # type: ignore
        await self._redis_client_sdk.redis.expire(
            task_key,
            expiry,
        )

    async def exists_task(self, task_id: TaskID) -> bool:
        n = await self._redis_client_sdk.redis.exists(_build_key(task_id))
        assert isinstance(n, int)  # nosec
        return n > 0

    async def get_task_metadata(self, task_id: TaskID) -> TaskMetadata | None:
        raw_result = await self._redis_client_sdk.redis.hget(_build_key(task_id), _CELERY_TASK_METADATA_KEY)  # type: ignore
        if not raw_result:
            return None

        try:
            return TaskMetadata.model_validate_json(raw_result)
        except ValidationError as exc:
            _logger.debug(
                "Failed to deserialize task metadata for task %s: %s", task_id, f"{exc}"
            )
            return None

    async def get_task_progress(self, task_id: TaskID) -> ProgressReport | None:
        raw_result = await self._redis_client_sdk.redis.hget(_build_key(task_id), _CELERY_TASK_PROGRESS_KEY)  # type: ignore
        if not raw_result:
            return None

        try:
            return ProgressReport.model_validate_json(raw_result)
        except ValidationError as exc:
            _logger.debug(
                "Failed to deserialize task progress for task %s: %s", task_id, f"{exc}"
            )
            return None

    async def list_tasks(self, task_context: TaskContext) -> list[Task]:
        search_key = (
            _CELERY_TASK_INFO_PREFIX
            + build_task_id_prefix(task_context)
            + _CELERY_TASK_ID_KEY_SEPARATOR
        )
        search_key_len = len(search_key)

        keys: list[str] = []
        pipeline = self._redis_client_sdk.redis.pipeline()
        async for key in self._redis_client_sdk.redis.scan_iter(
            match=search_key + "*", count=_CELERY_TASK_SCAN_COUNT_PER_BATCH
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
                task_metadata = TaskMetadata.model_validate_json(raw_metadata)
                tasks.append(
                    Task(
                        uuid=TaskUUID(key[search_key_len:]),
                        metadata=task_metadata,
                    )
                )

        return tasks

    async def remove_task(self, task_id: TaskID) -> None:
        await self._redis_client_sdk.redis.delete(_build_key(task_id))

    async def set_task_progress(self, task_id: TaskID, report: ProgressReport) -> None:
        await self._redis_client_sdk.redis.hset(
            name=_build_key(task_id),
            key=_CELERY_TASK_PROGRESS_KEY,
            value=report.model_dump_json(),
        )  # type: ignore
