import logging
from datetime import timedelta
from typing import Final

from celery.result import AsyncResult  # type: ignore[import-untyped]
from models_library.progress_bar import ProgressReport
from servicelib.redis._client import RedisClientSDK

from ..models import (
    TaskContext,
    TaskMetadata,
    TaskUUID,
    build_task_id,
    build_task_id_prefix,
)

_CELERY_TASK_INFO_PREFIX: Final[str] = "celery-task-info-"
_CELERY_TASK_ID_KEY_ENCODING = "utf-8"
_CELERY_TASK_ID_KEY_SEPARATOR: Final[str] = ":"
_CELERY_TASK_SCAN_COUNT_PER_BATCH: Final[int] = 10000
_CELERY_TASK_METADATA_KEY: Final[str] = "metadata"
_CELERY_TASK_PROGRESS_KEY: Final[str] = "progress"

_logger = logging.getLogger(__name__)


def _build_key(task_context: TaskContext, task_uuid: TaskUUID | None = None) -> str:
    if task_uuid is None:
        return _CELERY_TASK_INFO_PREFIX + build_task_id_prefix(task_context)
    return _CELERY_TASK_INFO_PREFIX + build_task_id(task_context, task_uuid)


class RedisTaskInfoStore:
    def __init__(self, redis_client_sdk: RedisClientSDK) -> None:
        self._redis_client_sdk = redis_client_sdk

    async def create(
        self,
        task_context: TaskContext,
        task_uuid: TaskUUID,
        task_metadata: TaskMetadata,
        expiry: timedelta,
    ) -> None:
        task_key = _build_key(task_context, task_uuid)
        await self._redis_client_sdk.redis.hset(
            name=task_key,
            key=_CELERY_TASK_METADATA_KEY,
            value=task_metadata.model_dump_json(),
        )  # type: ignore
        await self._redis_client_sdk.redis.expire(
            task_key,
            expiry,
        )

    async def exists(self, task_context: TaskContext, task_uuid: TaskUUID) -> bool:
        n = await self._redis_client_sdk.redis.exists(_build_key(task_context, task_uuid))  # type: ignore
        assert isinstance(n, int)  # nosec
        return n > 0

    async def get_metadata(
        self, task_context: TaskContext, task_uuid: TaskUUID
    ) -> TaskMetadata | None:
        result = await self._redis_client_sdk.redis.hget(_build_key(task_context, task_uuid), _CELERY_TASK_METADATA_KEY)  # type: ignore
        return TaskMetadata.model_validate_json(result) if result else None

    async def get_progress(
        self, task_context: TaskContext, task_uuid: TaskUUID
    ) -> ProgressReport | None:
        result = await self._redis_client_sdk.redis.hget(_build_key(task_context, task_uuid), _CELERY_TASK_PROGRESS_KEY)  # type: ignore
        return ProgressReport.model_validate_json(result) if result else None

    async def get_uuids(self, task_context: TaskContext) -> set[TaskUUID]:
        search_key = _build_key(task_context) + _CELERY_TASK_ID_KEY_SEPARATOR
        keys = set()
        async for key in self._redis_client_sdk.redis.scan_iter(
            match=search_key + "*", count=_CELERY_TASK_SCAN_COUNT_PER_BATCH
        ):
            # fake redis (tests) returns bytes, real redis returns str
            _key = (
                key.decode(_CELERY_TASK_ID_KEY_ENCODING)
                if isinstance(key, bytes)
                else key
            )
            keys.add(TaskUUID(_key.removeprefix(search_key)))
        return keys

    async def remove(self, task_context: TaskContext, task_uuid: TaskUUID) -> None:
        await self._redis_client_sdk.redis.delete(_build_key(task_context, task_uuid))  # type: ignore
        AsyncResult(build_task_id(task_context, task_uuid)).forget()

    async def set_progress(
        self, task_context: TaskContext, task_uuid: TaskUUID, report: ProgressReport
    ) -> None:
        await self._redis_client_sdk.redis.hset(
            name=_build_key(task_context, task_uuid),
            key=_CELERY_TASK_PROGRESS_KEY,
            value=report.model_dump_json(),
        )  # type: ignore
