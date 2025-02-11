from datetime import datetime, timezone
from typing import Final
from uuid import uuid4

from pydantic import NonNegativeInt

from ..redis._client import RedisClientSDK
from ._models import JobSchedule, ScheduleID, WorkerID

_ASYNC_SCHEDULER_PREFIX: Final[str] = "as::"

_JOB_SCHEDULES_PREFIX: Final[str] = "js:"
_SCHEDULER_WORKERS_PREFIX: Final[str] = "sw:"


def _build_key(*parts) -> str:
    return f"{_ASYNC_SCHEDULER_PREFIX}{''.join(parts)}"


class RedisJobSchedulerRepository:
    def __init__(self, redis_client_sdk: RedisClientSDK) -> None:
        self.redis_client_sdk = redis_client_sdk

    async def get_new_unique_identifier(self) -> ScheduleID:
        candidate_already_exists = True
        while candidate_already_exists:
            candidate = f"{uuid4()}"
            candidate_already_exists = await self.get_schedule(candidate) is not None
        return ScheduleID(candidate)

    async def save_schedule(
        self, schedule_id: ScheduleID, schedule: JobSchedule
    ) -> None:
        await self.redis_client_sdk.redis.set(
            _build_key(_JOB_SCHEDULES_PREFIX, schedule_id), schedule.model_dump_json()
        )

    async def get_schedule(self, schedule_id: ScheduleID) -> JobSchedule | None:
        raw_data = await self.redis_client_sdk.redis.get(
            _build_key(_JOB_SCHEDULES_PREFIX, schedule_id)
        )
        return JobSchedule.model_validate_json(raw_data) if raw_data else None

    async def update_worker_heartbeat(
        self, worker_id: WorkerID, ttl: NonNegativeInt
    ) -> None:
        await self.redis_client_sdk.redis.set(
            _build_key(_SCHEDULER_WORKERS_PREFIX, worker_id, ":heartbeat"),
            datetime.now(timezone.utc).isoformat(),
            ex=ttl,
        )

    async def get_worker_heartbeat(self, worker_id: WorkerID):
        last_heartbeat = await self.redis_client_sdk.redis.get(
            _build_key(_SCHEDULER_WORKERS_PREFIX, worker_id, ":heartbeat"),
        )
        return datetime.fromisoformat(f"{last_heartbeat}") if last_heartbeat else None
