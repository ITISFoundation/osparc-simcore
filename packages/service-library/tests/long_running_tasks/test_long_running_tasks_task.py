# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
import urllib.parse
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, Final

import pytest
from faker import Faker
from servicelib.long_running_tasks._errors import (
    TaskAlreadyRunningError,
    TaskCancelledError,
    TaskNotCompletedError,
    TaskNotFoundError,
)
from servicelib.long_running_tasks._models import (
    ProgressPercent,
    TaskProgress,
    TaskResult,
    TaskStatus,
)
from servicelib.long_running_tasks._task import TasksManager, start_task
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

_RETRY_PARAMS: dict[str, Any] = {
    "reraise": True,
    "wait": wait_fixed(0.1),
    "stop": stop_after_delay(60),
    "retry": retry_if_exception_type(AssertionError),
}


async def a_background_task(
    task_progress: TaskProgress,
    raise_when_finished: bool,
    total_sleep: int,
) -> int:
    """sleeps and raises an error or returns 42"""
    for i in range(total_sleep):
        await asyncio.sleep(1)
        task_progress.update(percent=ProgressPercent((i + 1) / total_sleep))
    if raise_when_finished:
        msg = "raised this error as instructed"
        raise RuntimeError(msg)

    return 42


async def fast_background_task(task_progress: TaskProgress) -> int:
    """this task does nothing and returns a constant"""
    return 42


async def failing_background_task(task_progress: TaskProgress):
    """this task does nothing and returns a constant"""
    msg = "failing asap"
    raise RuntimeError(msg)


TEST_CHECK_STALE_INTERVAL_S: Final[float] = 1


@pytest.fixture
async def tasks_manager() -> AsyncIterator[TasksManager]:
    tasks_manager = TasksManager(
        stale_task_check_interval_s=TEST_CHECK_STALE_INTERVAL_S,
        stale_task_detect_timeout_s=TEST_CHECK_STALE_INTERVAL_S,
    )
    yield tasks_manager
    await tasks_manager.close()


@pytest.mark.parametrize("check_task_presence_before", [True, False])
async def test_task_is_auto_removed(
    tasks_manager: TasksManager, check_task_presence_before: bool
):
    task_id = start_task(
        tasks_manager,
        a_background_task,
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
            for tasks in tasks_manager._tasks_groups.values():  # noqa: SLF001
                if task_id in tasks:
                    msg = "wait till no element is found any longer"
                    raise AssertionError(msg)

    with pytest.raises(TaskNotFoundError):
        tasks_manager.get_task_status(task_id, with_task_context=None)
    with pytest.raises(TaskNotFoundError):
        tasks_manager.get_task_result(task_id, with_task_context=None)
    with pytest.raises(TaskNotFoundError):
        tasks_manager.get_task_result_old(task_id)


async def test_checked_task_is_not_auto_removed(tasks_manager: TasksManager):
    task_id = start_task(
        tasks_manager,
        a_background_task,
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
    task_id = start_task(
        tasks_manager,
        a_background_task,
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
    task_id = start_task(
        tasks_manager,
        a_background_task,
        raise_when_finished=False,
        total_sleep=5 * TEST_CHECK_STALE_INTERVAL_S,
    )
    with pytest.raises(TaskNotCompletedError):
        tasks_manager.get_task_result(task_id, with_task_context=None)

    with pytest.raises(TaskNotCompletedError):
        tasks_manager.get_task_result_old(task_id)


async def test_unique_task_already_running(tasks_manager: TasksManager):
    async def unique_task(task_progress: TaskProgress):
        await asyncio.sleep(1)

    start_task(tasks_manager=tasks_manager, task=unique_task, unique=True)

    # ensure unique running task regardless of how many times it gets started
    with pytest.raises(TaskAlreadyRunningError) as exec_info:
        start_task(tasks_manager=tasks_manager, task=unique_task, unique=True)
    assert "must be unique, found: " in f"{exec_info.value}"


async def test_start_multiple_not_unique_tasks(tasks_manager: TasksManager):
    async def not_unique_task(task_progress: TaskProgress):
        await asyncio.sleep(1)

    for _ in range(5):
        start_task(tasks_manager=tasks_manager, task=not_unique_task)


def test_get_task_id():
    obj1 = TasksManager._create_task_id("")  # noqa: SLF001
    obj2 = TasksManager._create_task_id("")  # noqa: SLF001
    assert obj1 != obj2


async def test_get_status(tasks_manager: TasksManager):
    task_id = start_task(
        tasks_manager=tasks_manager,
        task=a_background_task,
        raise_when_finished=False,
        total_sleep=10,
    )
    task_status = tasks_manager.get_task_status(task_id, with_task_context=None)
    assert isinstance(task_status, TaskStatus)
    assert task_status.task_progress.message == ""
    assert task_status.task_progress.percent == 0.0
    assert task_status.done == False
    assert isinstance(task_status.started, datetime)


async def test_get_status_missing(tasks_manager: TasksManager):
    with pytest.raises(TaskNotFoundError) as exec_info:
        tasks_manager.get_task_status("missing_task_id", with_task_context=None)
    assert f"{exec_info.value}" == "No task with missing_task_id found"


async def test_get_result(tasks_manager: TasksManager):
    task_id = start_task(tasks_manager=tasks_manager, task=fast_background_task)
    await asyncio.sleep(0.1)
    result = tasks_manager.get_task_result(task_id, with_task_context=None)
    assert result == 42


async def test_get_result_old(tasks_manager: TasksManager):
    task_id = start_task(tasks_manager=tasks_manager, task=fast_background_task)
    await asyncio.sleep(0.1)
    result = tasks_manager.get_task_result_old(task_id)
    assert result == TaskResult(result=42, error=None)


async def test_get_result_missing(tasks_manager: TasksManager):
    with pytest.raises(TaskNotFoundError) as exec_info:
        tasks_manager.get_task_result("missing_task_id", with_task_context=None)
    assert f"{exec_info.value}" == "No task with missing_task_id found"


async def test_get_result_finished_with_error(tasks_manager: TasksManager):
    task_id = start_task(tasks_manager=tasks_manager, task=failing_background_task)
    # wait for result
    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:
            assert tasks_manager.get_task_status(task_id, with_task_context=None).done

    with pytest.raises(RuntimeError, match="failing asap"):
        tasks_manager.get_task_result(task_id, with_task_context=None)


async def test_get_result_old_finished_with_error(tasks_manager: TasksManager):
    task_id = start_task(tasks_manager=tasks_manager, task=failing_background_task)
    # wait for result
    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:
            assert tasks_manager.get_task_status(task_id, with_task_context=None).done

    task_result = tasks_manager.get_task_result_old(task_id)
    assert task_result.result is None
    assert task_result.error is not None
    assert task_result.error.startswith(f"Task {task_id} finished with exception:")
    assert "failing asap" in task_result.error


async def test_get_result_task_was_cancelled_multiple_times(
    tasks_manager: TasksManager,
):
    task_id = start_task(
        tasks_manager=tasks_manager,
        task=a_background_task,
        raise_when_finished=False,
        total_sleep=10,
    )
    for _ in range(5):
        await tasks_manager.cancel_task(task_id, with_task_context=None)

    with pytest.raises(
        TaskCancelledError, match=f"Task {task_id} was cancelled before completing"
    ):
        tasks_manager.get_task_result(task_id, with_task_context=None)


async def test_get_result_old_task_was_cancelled_multiple_times(
    tasks_manager: TasksManager,
):
    task_id = start_task(
        tasks_manager=tasks_manager,
        task=a_background_task,
        raise_when_finished=False,
        total_sleep=10,
    )
    for _ in range(5):
        await tasks_manager.cancel_task(task_id, with_task_context=None)

    task_result = tasks_manager.get_task_result_old(task_id)
    assert task_result.result is None
    assert task_result.error == f"Task {task_id} was cancelled before completing"


async def test_remove_task(tasks_manager: TasksManager):
    task_id = start_task(
        tasks_manager=tasks_manager,
        task=a_background_task,
        raise_when_finished=False,
        total_sleep=10,
    )
    tasks_manager.get_task_status(task_id, with_task_context=None)
    await tasks_manager.remove_task(task_id, with_task_context=None)
    with pytest.raises(TaskNotFoundError):
        tasks_manager.get_task_status(task_id, with_task_context=None)
    with pytest.raises(TaskNotFoundError):
        tasks_manager.get_task_result(task_id, with_task_context=None)
    with pytest.raises(TaskNotFoundError):
        tasks_manager.get_task_result_old(task_id)


async def test_remove_task_with_task_context(tasks_manager: TasksManager):
    TASK_CONTEXT = {"some_context": "some_value"}
    task_id = start_task(
        tasks_manager=tasks_manager,
        task=a_background_task,
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
    task_id = start_task(
        tasks_manager=tasks_manager,
        task=a_background_task,
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
            start_task(
                tasks_manager=tasks_manager,
                task=a_background_task,
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
    start_task(
        tasks_manager=tasks_manager,
        task=a_background_task,
        raise_when_finished=False,
        total_sleep=10,
    )
    start_task(
        tasks_manager=tasks_manager,
        task=a_background_task,
        raise_when_finished=False,
        total_sleep=10,
        task_context={"user_id": 213},
    )
    start_task(
        tasks_manager=tasks_manager,
        task=a_background_task,
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
    task_id = start_task(
        tasks_manager=tasks_manager,
        task=a_background_task,
        raise_when_finished=False,
        total_sleep=10,
        task_name=task_name,
    )
    assert task_id.startswith(urllib.parse.quote(task_name, safe=""))
