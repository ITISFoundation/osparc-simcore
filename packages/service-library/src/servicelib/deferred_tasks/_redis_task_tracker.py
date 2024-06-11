from typing import Final
from uuid import uuid4

from pydantic import NonNegativeInt

from ..redis import RedisClientSDK
from ..utils import logged_gather
from ._base_task_tracker import BaseTaskTracker
from ._models import TaskUID
from ._task_schedule import TaskScheduleModel

_TASK_TRACKER_PREFIX: Final[str] = "mm:"
_MAX_REDIS_CONCURRENCY: Final[NonNegativeInt] = 10


def _get_key(task_uid: TaskUID) -> str:
    return f"{_TASK_TRACKER_PREFIX}{task_uid}"


class RedisTaskTracker(BaseTaskTracker):
    def __init__(self, redis_client_sdk: RedisClientSDK) -> None:
        self.redis_client_sdk = redis_client_sdk

    async def get_new_unique_identifier(self) -> TaskUID:
        candidate_already_exists = True
        while candidate_already_exists:
            candidate = f"{uuid4()}"
            candidate_already_exists = (
                await self.redis_client_sdk.redis.get(_get_key(candidate)) is not None
            )
        return TaskUID(candidate)

    async def _get_raw(self, redis_key: str) -> TaskScheduleModel | None:
        found_data = await self.redis_client_sdk.redis.get(redis_key)
        return None if found_data is None else TaskScheduleModel.parse_raw(found_data)

    async def get(self, task_uid: TaskUID) -> TaskScheduleModel | None:
        return await self._get_raw(_get_key(task_uid))

    async def save(self, task_uid: TaskUID, task_schedule: TaskScheduleModel) -> None:
        await self.redis_client_sdk.redis.set(_get_key(task_uid), task_schedule.json())

    async def remove(self, task_uid: TaskUID) -> None:
        await self.redis_client_sdk.redis.delete(_get_key(task_uid))

    async def all(self) -> list[TaskScheduleModel]:
        return await logged_gather(
            *[
                self._get_raw(x)
                async for x in self.redis_client_sdk.redis.scan_iter(
                    match=f"{_TASK_TRACKER_PREFIX}*"
                )
            ],
            max_concurrency=_MAX_REDIS_CONCURRENCY,
        )
