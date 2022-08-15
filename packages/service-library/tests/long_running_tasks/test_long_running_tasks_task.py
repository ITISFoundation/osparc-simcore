# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
from asyncio import Task
from contextlib import asynccontextmanager
from datetime import datetime
from enum import Enum
from typing import AsyncIterable, AsyncIterator, Final, Optional

import pytest
from fastapi import status
from servicelib.long_running_tasks._errors import (
    TaskAlreadyRunningError,
    TaskCancelledError,
    TaskNotCompletedError,
    TaskNotFoundError,
)
from servicelib.long_running_tasks._models import (
    TaskId,
    TaskProgress,
    TaskResult,
    TaskStatus,
)
from servicelib.long_running_tasks._task import TasksManager, start_task
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

# UTILS


async def a_background_task(
    task_progress: TaskProgress,
    raise_when_finished: bool,
    total_sleep: int,
) -> int:
    """sleeps and raises an error or returns 42"""
    for i in range(total_sleep):
        await asyncio.sleep(1)
        task_progress.publish(percent=float((i + 1) / total_sleep))
    if raise_when_finished:
        raise RuntimeError("raised this error as instructed")

    return 42


async def fast_background_task(task_progress: TaskProgress) -> int:
    """this task does nothing and returns a constant"""
    return 42


async def failing_background_task(task_progress: TaskProgress) -> None:
    """this task does nothing and returns a constant"""
    raise RuntimeError("failing asap")


TEST_CHECK_STALE_INTERVAL_S: Final[float] = 1


@pytest.fixture
async def tasks_manager() -> AsyncIterator[TasksManager]:
    tasks_manager = TasksManager(
        stale_task_check_interval_s=TEST_CHECK_STALE_INTERVAL_S,
        stale_task_detect_timeout_s=TEST_CHECK_STALE_INTERVAL_S,
    )
    yield tasks_manager
    await tasks_manager.close()


async def test_unchecked_task_is_auto_removed(tasks_manager: TasksManager):
    task_id = start_task(
        tasks_manager,
        a_background_task,
        raise_when_finished=False,
        total_sleep=10 * TEST_CHECK_STALE_INTERVAL_S,
    )
    await asyncio.sleep(2 * TEST_CHECK_STALE_INTERVAL_S + 1)
    with pytest.raises(TaskNotFoundError):
        tasks_manager.get_task_status(task_id)


async def test_checked_task_is_not_auto_removed(tasks_manager: TasksManager):
    task_id = start_task(
        tasks_manager,
        a_background_task,
        raise_when_finished=False,
        total_sleep=5 * TEST_CHECK_STALE_INTERVAL_S,
    )
    async for attempt in AsyncRetrying(
        reraise=True,
        wait=wait_fixed(TEST_CHECK_STALE_INTERVAL_S / 10.0),
        stop=stop_after_delay(60),
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            status = tasks_manager.get_task_status(task_id)
            assert status.done, f"task {task_id} not complete"
    tasks_manager.get_task_result(task_id)


async def test_unique_task_already_running(tasks_manager: TasksManager) -> None:
    async def unique_task(task_progress: TaskProgress) -> None:
        await asyncio.sleep(1)

    start_task(tasks_manager=tasks_manager, handler=unique_task, unique=True)

    # ensure unique running task regardless of how many times it gets started
    for _ in range(5):
        with pytest.raises(TaskAlreadyRunningError) as exec_info:
            start_task(tasks_manager=tasks_manager, handler=unique_task, unique=True)


async def test_start_multiple_not_unique_tasks(tasks_manager: TasksManager) -> None:
    async def not_unique_task(task_progress: TaskProgress) -> None:
        await asyncio.sleep(1)

    for _ in range(5):
        start_task(tasks_manager=tasks_manager, handler=not_unique_task)


def test_get_task_id() -> None:
    assert TasksManager._create_task_id("") != TasksManager._create_task_id("")


async def test_get_status(tasks_manager: TasksManager) -> None:
    task_id = start_task(
        tasks_manager=tasks_manager,
        handler=a_background_task,
        raise_when_finished=False,
        total_sleep=10,
    )
    task_status = tasks_manager.get_task_status(task_id)
    assert isinstance(task_status, TaskStatus)
    assert task_status.task_progress.message == ""
    assert task_status.task_progress.percent == 0.0
    assert task_status.done == False
    assert isinstance(task_status.started, datetime)


async def test_get_status_missing(tasks_manager: TasksManager) -> None:
    with pytest.raises(TaskNotFoundError) as exec_info:
        tasks_manager.get_task_status("missing_task_id")
    assert f"{exec_info.value}" == "No task with missing_task_id found"


async def test_get_result(tasks_manager: TasksManager) -> None:
    task_id = start_task(tasks_manager=tasks_manager, handler=fast_background_task)
    await asyncio.sleep(0.1)
    result = tasks_manager.get_task_result(task_id)
    assert result == 42


async def test_get_result_old(tasks_manager: TasksManager) -> None:
    task_id = start_task(tasks_manager=tasks_manager, handler=fast_background_task)
    await asyncio.sleep(0.1)
    result = tasks_manager.get_task_result_old(task_id)
    assert result == TaskResult(result=42, error=None)


async def test_get_result_missing(tasks_manager: TasksManager) -> None:
    with pytest.raises(TaskNotFoundError) as exec_info:
        tasks_manager.get_task_result("missing_task_id")
    assert f"{exec_info.value}" == "No task with missing_task_id found"


async def test_get_result_finished_with_error(tasks_manager: TasksManager) -> None:
    task_id = start_task(tasks_manager=tasks_manager, handler=failing_background_task)

    can_continue = True
    while can_continue:
        try:
            tasks_manager.get_task_result(task_id)
        except TaskNotCompletedError:
            can_continue = False

        await asyncio.sleep(0.1)

    with pytest.raises(RuntimeError, match="failing asap"):
        tasks_manager.get_task_result(task_id)


async def test_get_result_old_finished_with_error(tasks_manager: TasksManager) -> None:
    task_id = start_task(tasks_manager=tasks_manager, handler=failing_background_task)

    can_continue = True
    while can_continue:
        try:
            tasks_manager.get_task_result(task_id)
        except TaskNotCompletedError:
            can_continue = False

        await asyncio.sleep(0.1)

    task_result = tasks_manager.get_task_result_old(task_id)
    assert task_result.result is None
    assert task_result.error is not None
    assert task_result.error.startswith(f"Task {task_id} finished with exception:")
    assert 'raise RuntimeError("failing asap")' in task_result.error


async def test_get_result_task_was_cancelled_multiple_times(
    tasks_manager: TasksManager,
) -> None:
    task_id = start_task(
        tasks_manager=tasks_manager,
        handler=a_background_task,
        raise_when_finished=False,
        total_sleep=10,
    )
    for _ in range(5):
        await tasks_manager.cancel_task(task_id)

    with pytest.raises(
        TaskCancelledError, match=f"Task {task_id} was cancelled before completing"
    ):
        tasks_manager.get_task_result(task_id)


async def test_get_result_old_task_was_cancelled_multiple_times(
    tasks_manager: TasksManager,
) -> None:
    task_id = start_task(
        tasks_manager=tasks_manager,
        handler=a_background_task,
        raise_when_finished=False,
        total_sleep=10,
    )
    for _ in range(5):
        await tasks_manager.cancel_task(task_id)

    task_result = tasks_manager.get_task_result_old(task_id)
    assert task_result.result is None
    assert task_result.error == f"Task {task_id} was cancelled before completing"


async def test_remove_ok(tasks_manager: TasksManager) -> None:
    task_id = start_task(
        tasks_manager=tasks_manager,
        handler=a_background_task,
        raise_when_finished=False,
        total_sleep=10,
    )
    # pylint: disable=protected-access
    assert tasks_manager._get_tracked_task(task_id)
    await tasks_manager.remove_task(task_id)
    with pytest.raises(TaskNotFoundError):
        assert tasks_manager._get_tracked_task(task_id)


# TESTS - stale task detection


class ExpectedTaskResult(str, Enum):
    RUNNING = "RUNNING"
    RAISE_ERROR = "RAISE_ERROR"
    HAS_RESULT = "HAS_RESULT"


BASE_SLEEP = 1.0
STATUS_POLL_INTERVAL = BASE_SLEEP * 0.2
TASK_CHECK_INTERVAL = BASE_SLEEP * 0.6
TASK_DETECT_TIMEOUT = BASE_SLEEP * 0.3


async def task_to_track(expected_task_result: ExpectedTaskResult) -> Optional[int]:
    if expected_task_result == ExpectedTaskResult.RUNNING:
        # sleeps for a very long amount of time
        await asyncio.sleep(BASE_SLEEP * 10)
    if expected_task_result == ExpectedTaskResult.RAISE_ERROR:
        raise RuntimeError("Task raised error as expected")
    if expected_task_result == ExpectedTaskResult.HAS_RESULT:
        return 42

    raise RuntimeError("OPS task finished running, this is unexpected!")


TASK_NAME = task_to_track.__name__


@pytest.fixture
async def stall_task_manager() -> AsyncIterable[TasksManager]:
    tasks_manager = TasksManager(
        stale_task_check_interval_s=TASK_CHECK_INTERVAL,
        stale_task_detect_timeout_s=TASK_DETECT_TIMEOUT,
    )

    yield tasks_manager

    await tasks_manager.close()


@asynccontextmanager
async def poll_status(
    tasks_manager: TasksManager, task_id: TaskId
) -> AsyncIterator[None]:
    continue_progress_check = True

    async def progress_checker() -> None:
        while continue_progress_check:
            task_status = tasks_manager.get_task_status(task_id)
            print(f"POLLING STATUS------> {task_status=}")
            await asyncio.sleep(STATUS_POLL_INTERVAL)

    progress_checker_task: Task = asyncio.create_task(progress_checker())
    try:
        yield
    finally:
        # close progress checker task when done with it
        assert progress_checker_task
        continue_progress_check = False
        await progress_checker_task


@pytest.mark.parametrize(
    "expected_task_result, is_done",
    [
        (ExpectedTaskResult.RUNNING, False),
        (ExpectedTaskResult.HAS_RESULT, True),
        (ExpectedTaskResult.RAISE_ERROR, True),
    ],
)
async def test_stall_task_is_tracked(
    stall_task_manager: TasksManager,
    expected_task_result: ExpectedTaskResult,
    is_done: bool,
) -> None:
    task = asyncio.create_task(task_to_track(expected_task_result))
    tracked_task = stall_task_manager.add_task(TASK_NAME, task, TaskProgress.create())
    assert len(stall_task_manager.get_task_group(TASK_NAME)) == 1

    async with poll_status(stall_task_manager, tracked_task.task_id):
        # let some time pass
        await asyncio.sleep(STATUS_POLL_INTERVAL)

        task_status: TaskStatus = stall_task_manager.get_task_status(
            tracked_task.task_id
        )
        assert task_status.done is is_done
    assert len(stall_task_manager.get_task_group(TASK_NAME)) == 1


@pytest.mark.parametrize(
    "expected_task_result",
    [
        ExpectedTaskResult.RUNNING,
        ExpectedTaskResult.HAS_RESULT,
        ExpectedTaskResult.RAISE_ERROR,
    ],
)
async def test_stall_task_not_tracked(
    stall_task_manager: TasksManager, expected_task_result: ExpectedTaskResult
) -> None:
    task = asyncio.create_task(task_to_track(expected_task_result))
    tracked_task = stall_task_manager.add_task(TASK_NAME, task, TaskProgress.create())
    assert len(stall_task_manager.get_task_group(TASK_NAME)) == 1
    # expected task still running
    await asyncio.sleep(TASK_CHECK_INTERVAL)
    assert len(stall_task_manager.get_task_group(TASK_NAME)) == 1

    # let task remove itself
    await asyncio.sleep(TASK_CHECK_INTERVAL * 2)

    # task will no longer be found
    with pytest.raises(TaskNotFoundError):
        stall_task_manager.get_task_status(tracked_task.task_id)
    # expect this to have been removed
    assert len(stall_task_manager.get_task_group(TASK_NAME)) == 0
