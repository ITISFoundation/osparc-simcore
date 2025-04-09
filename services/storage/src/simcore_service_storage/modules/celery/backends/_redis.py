import logging
from datetime import timedelta
from typing import Final

from celery.result import AsyncResult  # type: ignore[import-untyped]
from servicelib.redis._client import RedisClientSDK

from ..models import TaskContext, TaskID, TaskMetadata, TaskUUID, build_task_id_prefix

_CELERY_TASK_META_PREFIX: Final[str] = "celery-task-meta-"
_CELERY_TASK_METADATA_PREFIX: Final[str] = "celery-task-metadata-"
_CELERY_TASK_ID_KEY_ENCODING = "utf-8"
_CELERY_TASK_ID_KEY_SEPARATOR: Final[str] = ":"
_CELERY_TASK_SCAN_COUNT_PER_BATCH: Final[int] = 10000

_logger = logging.getLogger(__name__)


def _build_key(task_id: TaskID) -> str:
    return _CELERY_TASK_METADATA_PREFIX + task_id


class RedisTaskMetadataStore:
    def __init__(self, redis_client_sdk: RedisClientSDK) -> None:
        self._redis_client_sdk = redis_client_sdk

    async def exists(self, task_id: TaskID) -> bool:
        n = await self._redis_client_sdk.redis.exists(_build_key(task_id))
        assert isinstance(n, int)  # nosec
        return n > 0

    async def get(self, task_id: TaskID) -> TaskMetadata | None:
        result = await self._redis_client_sdk.redis.get(_build_key(task_id))
        return TaskMetadata.model_validate_json(result) if result else None

    async def get_uuids(self, task_context: TaskContext) -> set[TaskUUID]:
        search_key = (
            _CELERY_TASK_METADATA_PREFIX
            + build_task_id_prefix(task_context)
            + _CELERY_TASK_ID_KEY_SEPARATOR
        )
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

    async def remove(self, task_id: TaskID) -> None:
        await self._redis_client_sdk.redis.delete(_build_key(task_id))
        AsyncResult(_CELERY_TASK_META_PREFIX + task_id).forget()

    async def set(
        self, task_id: TaskID, task_metadata: TaskMetadata, expiry: timedelta
    ) -> None:
        await self._redis_client_sdk.redis.set(
            _build_key(task_id),
            task_metadata.model_dump_json(),
            ex=expiry,
        )
