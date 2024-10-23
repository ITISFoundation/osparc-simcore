# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument


from datetime import timedelta

import pytest
from pydantic import TypeAdapter
from servicelib.deferred_tasks._models import TaskUID
from servicelib.deferred_tasks._redis_task_tracker import RedisTaskTracker
from servicelib.deferred_tasks._task_schedule import TaskScheduleModel, TaskState
from servicelib.redis import RedisClientSDK
from servicelib.utils import logged_gather

pytest_simcore_core_services_selection = [
    "redis",
]


@pytest.fixture
def task_schedule() -> TaskScheduleModel:
    return TypeAdapter(TaskScheduleModel).validate_python(
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
    redis_client_sdk_deferred_tasks: RedisClientSDK,
    task_schedule: TaskScheduleModel,
):
    task_tracker = RedisTaskTracker(redis_client_sdk_deferred_tasks)

    task_uid: TaskUID = await task_tracker.get_new_unique_identifier()

    assert await task_tracker.get(task_uid) is None

    await task_tracker.save(task_uid, task_schedule)
    assert await task_tracker.get(task_uid) == task_schedule

    await task_tracker.remove(task_uid)
    assert await task_tracker.get(task_uid) is None


@pytest.mark.parametrize("count", [0, 1, 10, 100])
async def test_task_tracker_list_all_entries(
    redis_client_sdk_deferred_tasks: RedisClientSDK,
    task_schedule: TaskScheduleModel,
    count: int,
):
    task_tracker = RedisTaskTracker(redis_client_sdk_deferred_tasks)

    async def _make_entry() -> None:
        task_uid = await task_tracker.get_new_unique_identifier()
        await task_tracker.save(task_uid, task_schedule)

    await logged_gather(*(_make_entry() for _ in range(count)))

    entries = await task_tracker.all()
    assert len(entries) == count
    assert entries == [task_schedule for _ in range(count)]
