import pytest
from pydantic import TypeAdapter
from servicelib.job_scheduler._models import JobSchedule, ScheduleID
from servicelib.job_scheduler._redis_job_scheduler_repository import (
    RedisJobSchedulerRepository,
)
from servicelib.redis._client import RedisClientSDK

pytest_simcore_core_services_selection = [
    "redis",
]


@pytest.fixture
def job_schedule() -> JobSchedule:
    return TypeAdapter(JobSchedule).validate_python(
        {
            # "timeout": timedelta(seconds=1),
            # "execution_attempts": 1,
            # "class_unique_reference": "mock",
            # "start_context": {},
            # "state": TaskState.SCHEDULED,
            # "result": None,
        },
    )


async def test_job_scheduler_workflow(
    redis_client_sdk_job_scheduler: RedisClientSDK,
    job_schedule: JobSchedule,
):
    repo = RedisJobSchedulerRepository(redis_client_sdk_job_scheduler)

    schedule_id: ScheduleID = await repo.get_new_unique_identifier()

    assert await repo.get_schedule(schedule_id) is None
    await repo.save_schedule(schedule_id, job_schedule)
    assert await repo.get_schedule(schedule_id) == job_schedule
