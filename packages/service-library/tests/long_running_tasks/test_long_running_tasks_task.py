# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
import urllib.parse
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any, Final

import pytest
from faker import Faker
from models_library.api_schemas_long_running_tasks.base import ProgressMessage
from servicelib.long_running_tasks import lrt_api
from servicelib.long_running_tasks.errors import (
    TaskAlreadyRunningError,
    TaskNotCompletedError,
    TaskNotFoundError,
    TaskNotRegisteredError,
)
from servicelib.long_running_tasks.models import TaskContext, TaskProgress, TaskStatus
from servicelib.long_running_tasks.task import TaskRegistry, TasksManager
from settings_library.redis import RedisSettings
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
        await progress.update(percent=(i + 1) / total_sleep)
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
def empty_context() -> TaskContext:
    return {}


@pytest.fixture
async def get_tasks_manager() -> (
    AsyncIterator[Callable[[RedisSettings], Awaitable[TasksManager]]]
):
    managers: list[TasksManager] = []

    async def _(redis_settings: RedisSettings) -> TasksManager:
        tasks_manager = TasksManager(
            stale_task_check_interval=timedelta(seconds=TEST_CHECK_STALE_INTERVAL_S),
            stale_task_detect_timeout=timedelta(seconds=TEST_CHECK_STALE_INTERVAL_S),
            redis_settings=redis_settings,
            namespace="test",
        )
        await tasks_manager.setup()
        managers.append(tasks_manager)
        return tasks_manager

    yield _

    for manager in managers:
        await manager.teardown()


@pytest.fixture
async def tasks_manager(
    use_in_memory_redis: RedisSettings,
    get_tasks_manager: Callable[[RedisSettings], Awaitable[TasksManager]],
) -> TasksManager:
    return await get_tasks_manager(use_in_memory_redis)


@pytest.mark.parametrize("check_task_presence_before", [True, False])
async def test_task_is_auto_removed(
    tasks_manager: TasksManager,
    check_task_presence_before: bool,
    empty_context: TaskContext,
):
    task_id = await lrt_api.start_task(
        tasks_manager,
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=10 * TEST_CHECK_STALE_INTERVAL_S,
        task_context=empty_context,
    )

    if check_task_presence_before:
        # immediately after starting the task is still there
        task_status = await tasks_manager.get_task_status(
            task_id, with_task_context=empty_context
        )
        assert task_status

    # wait for task to be automatically removed
    # meaning no calls via the manager methods are received
    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:
            if (
                await tasks_manager._tasks_data.get_task_data(task_id)  # noqa: SLF001
                is not None
            ):
                msg = "wait till no element is found any longer"
                raise TryAgain(msg)

    with pytest.raises(TaskNotFoundError):
        await tasks_manager.get_task_status(task_id, with_task_context=empty_context)
    with pytest.raises(TaskNotFoundError):
        await tasks_manager.get_task_result(task_id, with_task_context=empty_context)


async def test_checked_task_is_not_auto_removed(
    tasks_manager: TasksManager, empty_context: TaskContext
):
    task_id = await lrt_api.start_task(
        tasks_manager,
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=5 * TEST_CHECK_STALE_INTERVAL_S,
        task_context=empty_context,
    )
    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:
            status = await tasks_manager.get_task_status(
                task_id, with_task_context=empty_context
            )
            assert status.done, f"task {task_id} not complete"
    result = await tasks_manager.get_task_result(
        task_id, with_task_context=empty_context
    )
    assert result


async def test_fire_and_forget_task_is_not_auto_removed(
    tasks_manager: TasksManager, empty_context: TaskContext
):
    task_id = await lrt_api.start_task(
        tasks_manager,
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=5 * TEST_CHECK_STALE_INTERVAL_S,
        fire_and_forget=True,
        task_context=empty_context,
    )
    await asyncio.sleep(3 * TEST_CHECK_STALE_INTERVAL_S)
    # the task shall still be present even if we did not check the status before
    status = await tasks_manager.get_task_status(
        task_id, with_task_context=empty_context
    )
    assert not status.done, "task was removed although it is fire and forget"
    # the task shall finish
    await asyncio.sleep(4 * TEST_CHECK_STALE_INTERVAL_S)
    # get the result
    task_result = await tasks_manager.get_task_result(
        task_id, with_task_context=empty_context
    )
    assert task_result == 42


async def test_get_result_of_unfinished_task_raises(
    tasks_manager: TasksManager, empty_context: TaskContext
):
    task_id = await lrt_api.start_task(
        tasks_manager,
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=5 * TEST_CHECK_STALE_INTERVAL_S,
        task_context=empty_context,
    )
    with pytest.raises(TaskNotCompletedError):
        await tasks_manager.get_task_result(task_id, with_task_context=empty_context)


async def test_unique_task_already_running(
    tasks_manager: TasksManager, empty_context: TaskContext
):
    async def unique_task(progress: TaskProgress):
        _ = progress
        await asyncio.sleep(1)

    TaskRegistry.register(unique_task)

    await lrt_api.start_task(
        tasks_manager, unique_task.__name__, unique=True, task_context=empty_context
    )

    # ensure unique running task regardless of how many times it gets started
    with pytest.raises(TaskAlreadyRunningError) as exec_info:
        await lrt_api.start_task(
            tasks_manager, unique_task.__name__, unique=True, task_context=empty_context
        )
    assert "must be unique, found: " in f"{exec_info.value}"

    TaskRegistry.unregister(unique_task)


async def test_start_multiple_not_unique_tasks(
    tasks_manager: TasksManager, empty_context: TaskContext
):
    async def not_unique_task(progress: TaskProgress):
        await asyncio.sleep(1)

    TaskRegistry.register(not_unique_task)

    for _ in range(5):
        await lrt_api.start_task(
            tasks_manager, not_unique_task.__name__, task_context=empty_context
        )

    TaskRegistry.unregister(not_unique_task)


@pytest.mark.parametrize("is_unique", [True, False])
async def test_get_task_id(tasks_manager: TasksManager, faker: Faker, is_unique: bool):
    obj1 = tasks_manager._get_task_id(faker.word(), is_unique=is_unique)  # noqa: SLF001
    obj2 = tasks_manager._get_task_id(faker.word(), is_unique=is_unique)  # noqa: SLF001
    assert obj1 != obj2


async def test_get_status(tasks_manager: TasksManager, empty_context: TaskContext):
    task_id = await lrt_api.start_task(
        tasks_manager,
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=10,
        task_context=empty_context,
    )
    task_status = await tasks_manager.get_task_status(
        task_id, with_task_context=empty_context
    )
    assert isinstance(task_status, TaskStatus)
    assert isinstance(task_status.task_progress.message, ProgressMessage)
    assert task_status.task_progress.percent == 0.0
    assert task_status.done is False
    assert isinstance(task_status.started, datetime)


async def test_get_status_missing(
    tasks_manager: TasksManager, empty_context: TaskContext
):
    with pytest.raises(TaskNotFoundError) as exec_info:
        await tasks_manager.get_task_status(
            "missing_task_id", with_task_context=empty_context
        )
    assert f"{exec_info.value}" == "No task with missing_task_id found"


async def test_get_result(tasks_manager: TasksManager, empty_context: TaskContext):
    task_id = await lrt_api.start_task(
        tasks_manager, fast_background_task.__name__, task_context=empty_context
    )

    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:
            status = await tasks_manager.get_task_status(
                task_id, with_task_context=empty_context
            )
            assert status.done is True

    result = await tasks_manager.get_task_result(
        task_id, with_task_context=empty_context
    )
    assert result == 42


async def test_get_result_missing(
    tasks_manager: TasksManager, empty_context: TaskContext
):
    with pytest.raises(TaskNotFoundError) as exec_info:
        await tasks_manager.get_task_result(
            "missing_task_id", with_task_context=empty_context
        )
    assert f"{exec_info.value}" == "No task with missing_task_id found"


async def test_get_result_finished_with_error(
    tasks_manager: TasksManager, empty_context: TaskContext
):
    task_id = await lrt_api.start_task(
        tasks_manager, failing_background_task.__name__, task_context=empty_context
    )
    # wait for result
    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:
            assert (
                await tasks_manager.get_task_status(
                    task_id, with_task_context=empty_context
                )
            ).done

    with pytest.raises(RuntimeError, match="failing asap"):
        await tasks_manager.get_task_result(task_id, with_task_context=empty_context)


async def test_cancel_task_from_different_manager(
    use_in_memory_redis: RedisSettings,
    get_tasks_manager: Callable[[RedisSettings], Awaitable[TasksManager]],
    empty_context: TaskContext,
):
    manager_1 = await get_tasks_manager(use_in_memory_redis)
    manager_2 = await get_tasks_manager(use_in_memory_redis)
    manager_3 = await get_tasks_manager(use_in_memory_redis)

    task_id = await lrt_api.start_task(
        manager_1,
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=1,
        task_context=empty_context,
    )

    # wati for task to complete
    for manager in (manager_1, manager_2, manager_3):
        status = await manager.get_task_status(task_id, empty_context)
        assert status.done is False

    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:
            for manager in (manager_1, manager_2, manager_3):
                status = await manager.get_task_status(task_id, empty_context)
                assert status.done is True

    # check all provide the same result
    for manager in (manager_1, manager_2, manager_3):
        task_result = await manager.get_task_result(task_id, empty_context)
        assert task_result == 42


async def test_remove_task(tasks_manager: TasksManager, empty_context: TaskContext):
    task_id = await lrt_api.start_task(
        tasks_manager,
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=10,
        task_context=empty_context,
    )
    await tasks_manager.get_task_status(task_id, with_task_context=empty_context)
    await tasks_manager.remove_task(task_id, with_task_context=empty_context)
    with pytest.raises(TaskNotFoundError):
        await tasks_manager.get_task_status(task_id, with_task_context=empty_context)
    with pytest.raises(TaskNotFoundError):
        await tasks_manager.get_task_result(task_id, with_task_context=empty_context)


async def test_remove_task_with_task_context(
    tasks_manager: TasksManager, empty_context: TaskContext
):
    task_id = await lrt_api.start_task(
        tasks_manager,
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=10,
        task_context=empty_context,
    )
    # getting status fails if wrong task context given
    with pytest.raises(TaskNotFoundError):
        await tasks_manager.get_task_status(
            task_id, with_task_context={"wrong_task_context": 12}
        )
    await tasks_manager.get_task_status(task_id, with_task_context=empty_context)

    # removing task fails if wrong task context given
    with pytest.raises(TaskNotFoundError):
        await tasks_manager.remove_task(
            task_id, with_task_context={"wrong_task_context": 12}
        )
    await tasks_manager.remove_task(task_id, with_task_context=empty_context)


async def test_remove_unknown_task(
    tasks_manager: TasksManager, empty_context: TaskContext
):
    with pytest.raises(TaskNotFoundError):
        await tasks_manager.remove_task("invalid_id", with_task_context=empty_context)

    await tasks_manager.remove_task(
        "invalid_id", with_task_context=empty_context, reraise_errors=False
    )


async def test__cancelled_tasks_worker_equivalent_of_cancellation_from_a_different_process(
    tasks_manager: TasksManager, empty_context: TaskContext
):
    task_id = await lrt_api.start_task(
        tasks_manager,
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=10,
        task_context=empty_context,
    )
    await tasks_manager._tasks_data.set_as_cancelled(  # noqa: SLF001
        task_id, with_task_context=empty_context
    )

    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:  # noqa: SIM117
            with pytest.raises(TaskNotFoundError):
                assert (
                    await tasks_manager.get_task_status(task_id, empty_context) is None
                )


async def test_list_tasks(tasks_manager: TasksManager, empty_context: TaskContext):
    assert await tasks_manager.list_tasks(with_task_context=empty_context) == []
    # start a bunch of tasks
    NUM_TASKS = 10
    task_ids = []
    for _ in range(NUM_TASKS):
        task_ids.append(  # noqa: PERF401
            await lrt_api.start_task(
                tasks_manager,
                a_background_task.__name__,
                raise_when_finished=False,
                total_sleep=10,
                task_context=empty_context,
            )
        )
    assert (
        len(await tasks_manager.list_tasks(with_task_context=empty_context))
        == NUM_TASKS
    )
    for task_index, task_id in enumerate(task_ids):
        await tasks_manager.remove_task(task_id, with_task_context=empty_context)
        assert len(
            await tasks_manager.list_tasks(with_task_context=empty_context)
        ) == NUM_TASKS - (task_index + 1)


async def test_list_tasks_filtering(
    tasks_manager: TasksManager, empty_context: TaskContext
):
    await lrt_api.start_task(
        tasks_manager,
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=10,
        task_context=empty_context,
    )
    await lrt_api.start_task(
        tasks_manager,
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=10,
        task_context={"user_id": 213},
    )
    await lrt_api.start_task(
        tasks_manager,
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=10,
        task_context={"user_id": 213, "product": "osparc"},
    )
    assert len(await tasks_manager.list_tasks(with_task_context=empty_context)) == 3
    assert len(await tasks_manager.list_tasks(with_task_context={"user_id": 213})) == 1
    assert (
        len(
            await tasks_manager.list_tasks(
                with_task_context={"user_id": 213, "product": "osparc"}
            )
        )
        == 1
    )
    assert (
        len(
            await tasks_manager.list_tasks(
                with_task_context={"user_id": 120, "product": "osparc"}
            )
        )
        == 0
    )


async def test_define_task_name(tasks_manager: TasksManager, faker: Faker):
    task_name = faker.name()
    task_id = await lrt_api.start_task(
        tasks_manager,
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=10,
        task_name=task_name,
    )
    assert urllib.parse.quote(task_name, safe="") in task_id


async def test_start_not_registered_task(tasks_manager: TasksManager):
    with pytest.raises(TaskNotRegisteredError):
        await lrt_api.start_task(tasks_manager, "not_registered_task")
