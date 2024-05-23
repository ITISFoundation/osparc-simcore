# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument


from collections.abc import AsyncIterable
from datetime import timedelta

import pytest
from pydantic import parse_obj_as
from servicelib.deferred_tasks._models import TaskUID
from servicelib.deferred_tasks._redis_task_tracker import RedisTaskTracker
from servicelib.deferred_tasks._task_schedule import TaskSchedule, TaskState
from servicelib.redis import RedisClientSDKHealthChecked
from servicelib.utils import logged_gather
from settings_library.redis import RedisDatabase, RedisSettings

pytest_simcore_core_services_selection = [
    "redis",
]


@pytest.fixture
async def scheduling_redis_sdk(
    redis_service: RedisSettings,
) -> AsyncIterable[RedisClientSDKHealthChecked]:
    redis_sdk = RedisClientSDKHealthChecked(
        redis_service.build_redis_dsn(RedisDatabase.DEFERRED_TASKS)
    )
    await redis_sdk.redis.flushall()
    yield redis_sdk
    await redis_sdk.redis.flushall()


@pytest.fixture
def task_schedule() -> TaskSchedule:
    return parse_obj_as(
        TaskSchedule,
        {
            "timeout": timedelta(seconds=1),
            "execution_attempts": 1,
            "class_unique_reference": "mock",
            "start_context": {},
            "state": TaskState.SCHEDULED,
            "result": None,
        },
    )


async def test_task_tracker_workflow(
    scheduling_redis_sdk: RedisClientSDKHealthChecked, task_schedule: TaskSchedule
):
    task_tracker = RedisTaskTracker(scheduling_redis_sdk)

    task_uid: TaskUID = await task_tracker.get_new_unique_identifier()

    assert await task_tracker.get(task_uid) is None

    await task_tracker.save(task_uid, task_schedule)
    assert await task_tracker.get(task_uid) == task_schedule

    await task_tracker.remove(task_uid)
    assert await task_tracker.get(task_uid) is None


@pytest.mark.parametrize("count", [0, 1, 10, 100])
async def test_task_tracker_list_all_entries(
    scheduling_redis_sdk: RedisClientSDKHealthChecked,
    task_schedule: TaskSchedule,
    count: int,
):
    task_tracker = RedisTaskTracker(scheduling_redis_sdk)

    async def _make_entry() -> None:
        task_uid = await task_tracker.get_new_unique_identifier()
        await task_tracker.save(task_uid, task_schedule)

    await logged_gather(*(_make_entry() for _ in range(count)))

    entries = await task_tracker.list()
    assert len(entries) == count
    assert entries == [task_schedule for _ in range(count)]
