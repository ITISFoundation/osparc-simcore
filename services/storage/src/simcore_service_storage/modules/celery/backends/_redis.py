from typing import Final

from servicelib.redis._client import RedisClientSDK

from ..models import TaskContext, TaskData, TaskID, TaskUUID, build_task_id_prefix

_CELERY_TASK_META_PREFIX: Final[str] = "celery-task-meta-"
_CELERY_TASK_ID_KEY_SEPARATOR: Final[str] = ":"
_CELERY_TASK_SCAN_COUNT_PER_BATCH: Final[int] = 10000
_CELERY_TASK_ID_KEY_ENCODING = "utf-8"


class RedisTaskStore:
    def __init__(self, redis_client_sdk: RedisClientSDK) -> None:
        self._redis_client_sdk = redis_client_sdk

    async def get_task_uuids(self, task_context: TaskContext) -> set[TaskUUID]:
        search_key = build_task_id_prefix(task_context) + _CELERY_TASK_ID_KEY_SEPARATOR
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

    async def task_exists(self, task_id: TaskID) -> bool:
        n = await self._redis_client_sdk.redis.exists(task_id)
        assert isinstance(n, int)  # nosec
        return n > 0

    async def set_task(self, task_id: TaskID, task_data: TaskData) -> None:
        await self._redis_client_sdk.redis.set(
            _CELERY_TASK_META_PREFIX + task_id,
            task_data.model_dump_json(),
        )
