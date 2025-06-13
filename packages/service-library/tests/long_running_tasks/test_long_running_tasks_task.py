# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
import urllib.parse
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from typing import Any, Final

import pytest
from faker import Faker
from servicelib.long_running_tasks.errors import (
    TaskAlreadyRunningError,
    TaskCancelledError,
    TaskNotCompletedError,
    TaskNotFoundError,
    TaskNotRegisteredError,
)
from servicelib.long_running_tasks.models import TaskProgress, TaskStatus
from servicelib.long_running_tasks.task import TaskRegistry, TasksManager
from tenacity import TryAgain
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

_RETRY_PARAMS: dict[str, Any] = {
    "reraise": True,
    "wait": wait_fixed(0.1),
    "stop": stop_after_delay(60),
    "retry": retry_if_exception_type((AssertionError, TryAgain)),
}


async def a_background_task(
    progress: TaskProgress,
    raise_when_finished: bool,
    total_sleep: int,
) -> int:
    """sleeps and raises an error or returns 42"""
    for i in range(total_sleep):
        await asyncio.sleep(1)
        progress.update(percent=(i + 1) / total_sleep)
    if raise_when_finished:
        msg = "raised this error as instructed"
        raise RuntimeError(msg)

    return 42


async def fast_background_task(progress: TaskProgress) -> int:
    """this task does nothing and returns a constant"""
    return 42


async def failing_background_task(progress: TaskProgress):
    """this task does nothing and returns a constant"""
    msg = "failing asap"
    raise RuntimeError(msg)


TaskRegistry.register(a_background_task)
TaskRegistry.register(fast_background_task)
TaskRegistry.register(failing_background_task)

TEST_CHECK_STALE_INTERVAL_S: Final[float] = 1


@pytest.fixture
async def tasks_manager() -> AsyncIterator[TasksManager]:
    tasks_manager = TasksManager(
        stale_task_check_interval=timedelta(seconds=TEST_CHECK_STALE_INTERVAL_S),
        stale_task_detect_timeout=timedelta(seconds=TEST_CHECK_STALE_INTERVAL_S),
    )
    await tasks_manager.setup()
    yield tasks_manager
    await tasks_manager.teardown()


@pytest.mark.parametrize("check_task_presence_before", [True, False])
async def test_task_is_auto_removed(
    tasks_manager: TasksManager, check_task_presence_before: bool
):
    task_id = tasks_manager.start_task(
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=10 * TEST_CHECK_STALE_INTERVAL_S,
    )

    if check_task_presence_before:
        # immediately after starting the task is still there
        task_status = tasks_manager.get_task_status(task_id, with_task_context=None)
        assert task_status

    # wait for task to be automatically removed
    # meaning no calls via the manager methods are received
    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:
            if task_id in tasks_manager._tracked_tasks:  # noqa: SLF001
                msg = "wait till no element is found any longer"
                raise TryAgain(msg)

    with pytest.raises(TaskNotFoundError):
        tasks_manager.get_task_status(task_id, with_task_context=None)
    with pytest.raises(TaskNotFoundError):
        tasks_manager.get_task_result(task_id, with_task_context=None)


async def test_checked_task_is_not_auto_removed(tasks_manager: TasksManager):
    task_id = tasks_manager.start_task(
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=5 * TEST_CHECK_STALE_INTERVAL_S,
    )
    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:
            status = tasks_manager.get_task_status(task_id, with_task_context=None)
            assert status.done, f"task {task_id} not complete"
    result = tasks_manager.get_task_result(task_id, with_task_context=None)
    assert result


async def test_fire_and_forget_task_is_not_auto_removed(tasks_manager: TasksManager):
    task_id = tasks_manager.start_task(
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=5 * TEST_CHECK_STALE_INTERVAL_S,
        fire_and_forget=True,
    )
    await asyncio.sleep(3 * TEST_CHECK_STALE_INTERVAL_S)
    # the task shall still be present even if we did not check the status before
    status = tasks_manager.get_task_status(task_id, with_task_context=None)
    assert not status.done, "task was removed although it is fire and forget"
    # the task shall finish
    await asyncio.sleep(3 * TEST_CHECK_STALE_INTERVAL_S)
    # get the result
    task_result = tasks_manager.get_task_result(task_id, with_task_context=None)
    assert task_result == 42


async def test_get_result_of_unfinished_task_raises(tasks_manager: TasksManager):
    task_id = tasks_manager.start_task(
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=5 * TEST_CHECK_STALE_INTERVAL_S,
    )
    with pytest.raises(TaskNotCompletedError):
        tasks_manager.get_task_result(task_id, with_task_context=None)


async def test_unique_task_already_running(tasks_manager: TasksManager):
    async def unique_task(progress: TaskProgress):
        _ = progress
        await asyncio.sleep(1)

    TaskRegistry.register(unique_task)

    tasks_manager.start_task(unique_task.__name__, unique=True)

    # ensure unique running task regardless of how many times it gets started
    with pytest.raises(TaskAlreadyRunningError) as exec_info:
        tasks_manager.start_task(unique_task.__name__, unique=True)
    assert "must be unique, found: " in f"{exec_info.value}"

    TaskRegistry.unregister(unique_task)


async def test_start_multiple_not_unique_tasks(tasks_manager: TasksManager):
    async def not_unique_task(progress: TaskProgress):
        await asyncio.sleep(1)

    TaskRegistry.register(not_unique_task)

    for _ in range(5):
        tasks_manager.start_task(not_unique_task.__name__)

    TaskRegistry.unregister(not_unique_task)


@pytest.mark.parametrize("is_unique", [True, False])
def test_get_task_id(tasks_manager: TasksManager, faker: Faker, is_unique: bool):
    obj1 = tasks_manager._get_task_id(faker.word(), is_unique=is_unique)  # noqa: SLF001
    obj2 = tasks_manager._get_task_id(faker.word(), is_unique=is_unique)  # noqa: SLF001
    assert obj1 != obj2


async def test_get_status(tasks_manager: TasksManager):
    task_id = tasks_manager.start_task(
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=10,
    )
    task_status = tasks_manager.get_task_status(task_id, with_task_context=None)
    assert isinstance(task_status, TaskStatus)
    assert task_status.task_progress.message == ""
    assert task_status.task_progress.percent == 0.0
    assert task_status.done is False
    assert isinstance(task_status.started, datetime)


async def test_get_status_missing(tasks_manager: TasksManager):
    with pytest.raises(TaskNotFoundError) as exec_info:
        tasks_manager.get_task_status("missing_task_id", with_task_context=None)
    assert f"{exec_info.value}" == "No task with missing_task_id found"


async def test_get_result(tasks_manager: TasksManager):
    task_id = tasks_manager.start_task(fast_background_task.__name__)
    await asyncio.sleep(0.1)
    result = tasks_manager.get_task_result(task_id, with_task_context=None)
    assert result == 42


async def test_get_result_missing(tasks_manager: TasksManager):
    with pytest.raises(TaskNotFoundError) as exec_info:
        tasks_manager.get_task_result("missing_task_id", with_task_context=None)
    assert f"{exec_info.value}" == "No task with missing_task_id found"


async def test_get_result_finished_with_error(tasks_manager: TasksManager):
    task_id = tasks_manager.start_task(failing_background_task.__name__)
    # wait for result
    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:
            assert tasks_manager.get_task_status(task_id, with_task_context=None).done

    with pytest.raises(RuntimeError, match="failing asap"):
        tasks_manager.get_task_result(task_id, with_task_context=None)


async def test_get_result_task_was_cancelled_multiple_times(
    tasks_manager: TasksManager,
):
    task_id = tasks_manager.start_task(
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=10,
    )
    for _ in range(5):
        await tasks_manager.cancel_task(task_id, with_task_context=None)

    with pytest.raises(
        TaskCancelledError, match=f"Task {task_id} was cancelled before completing"
    ):
        tasks_manager.get_task_result(task_id, with_task_context=None)


async def test_remove_task(tasks_manager: TasksManager):
    task_id = tasks_manager.start_task(
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=10,
    )
    tasks_manager.get_task_status(task_id, with_task_context=None)
    await tasks_manager.remove_task(task_id, with_task_context=None)
    with pytest.raises(TaskNotFoundError):
        tasks_manager.get_task_status(task_id, with_task_context=None)
    with pytest.raises(TaskNotFoundError):
        tasks_manager.get_task_result(task_id, with_task_context=None)


async def test_remove_task_with_task_context(tasks_manager: TasksManager):
    TASK_CONTEXT = {"some_context": "some_value"}
    task_id = tasks_manager.start_task(
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=10,
        task_context=TASK_CONTEXT,
    )
    # getting status fails if wrong task context given
    with pytest.raises(TaskNotFoundError):
        tasks_manager.get_task_status(
            task_id, with_task_context={"wrong_task_context": 12}
        )
    tasks_manager.get_task_status(task_id, with_task_context=TASK_CONTEXT)

    # removing task fails if wrong task context given
    with pytest.raises(TaskNotFoundError):
        await tasks_manager.remove_task(
            task_id, with_task_context={"wrong_task_context": 12}
        )
    await tasks_manager.remove_task(task_id, with_task_context=TASK_CONTEXT)


async def test_remove_unknown_task(tasks_manager: TasksManager):
    with pytest.raises(TaskNotFoundError):
        await tasks_manager.remove_task("invalid_id", with_task_context=None)

    await tasks_manager.remove_task(
        "invalid_id", with_task_context=None, reraise_errors=False
    )


async def test_cancel_task_with_task_context(tasks_manager: TasksManager):
    TASK_CONTEXT = {"some_context": "some_value"}
    task_id = tasks_manager.start_task(
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=10,
        task_context=TASK_CONTEXT,
    )
    # getting status fails if wrong task context given
    with pytest.raises(TaskNotFoundError):
        tasks_manager.get_task_status(
            task_id, with_task_context={"wrong_task_context": 12}
        )
    # getting status fails if wrong task context given
    with pytest.raises(TaskNotFoundError):
        await tasks_manager.cancel_task(
            task_id, with_task_context={"wrong_task_context": 12}
        )
    await tasks_manager.cancel_task(task_id, with_task_context=TASK_CONTEXT)


async def test_list_tasks(tasks_manager: TasksManager):
    assert tasks_manager.list_tasks(with_task_context=None) == []
    # start a bunch of tasks
    NUM_TASKS = 10
    task_ids = []
    for _ in range(NUM_TASKS):
        task_ids.append(  # noqa: PERF401
            tasks_manager.start_task(
                a_background_task.__name__,
                raise_when_finished=False,
                total_sleep=10,
            )
        )
    assert len(tasks_manager.list_tasks(with_task_context=None)) == NUM_TASKS
    for task_index, task_id in enumerate(task_ids):
        await tasks_manager.remove_task(task_id, with_task_context=None)
        assert len(tasks_manager.list_tasks(with_task_context=None)) == NUM_TASKS - (
            task_index + 1
        )


async def test_list_tasks_filtering(tasks_manager: TasksManager):
    tasks_manager.start_task(
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=10,
    )
    tasks_manager.start_task(
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=10,
        task_context={"user_id": 213},
    )
    tasks_manager.start_task(
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=10,
        task_context={"user_id": 213, "product": "osparc"},
    )
    assert len(tasks_manager.list_tasks(with_task_context=None)) == 3
    assert len(tasks_manager.list_tasks(with_task_context={"user_id": 213})) == 1
    assert (
        len(
            tasks_manager.list_tasks(
                with_task_context={"user_id": 213, "product": "osparc"}
            )
        )
        == 1
    )
    assert (
        len(
            tasks_manager.list_tasks(
                with_task_context={"user_id": 120, "product": "osparc"}
            )
        )
        == 0
    )


async def test_define_task_name(tasks_manager: TasksManager, faker: Faker):
    task_name = faker.name()
    task_id = tasks_manager.start_task(
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=10,
        task_name=task_name,
    )
    assert urllib.parse.quote(task_name, safe="") in task_id


async def test_start_not_registered_task(tasks_manager: TasksManager):
    with pytest.raises(TaskNotRegisteredError):
        tasks_manager.start_task("not_registered_task")
