# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
import urllib.parse
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

import pytest
from faker import Faker
from models_library.api_schemas_long_running_tasks.base import ProgressMessage
from servicelib.long_running_tasks import lrt_api
from servicelib.long_running_tasks._serialization import (
    loads,
)
from servicelib.long_running_tasks.base_long_running_manager import (
    BaseLongRunningManager,
)
from servicelib.long_running_tasks.errors import (
    TaskAlreadyRunningError,
    TaskNotCompletedError,
    TaskNotFoundError,
    TaskNotRegisteredError,
)
from servicelib.long_running_tasks.models import (
    LRTNamespace,
    ResultField,
    TaskContext,
    TaskProgress,
    TaskStatus,
)
from servicelib.long_running_tasks.task import TaskRegistry
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from tenacity import TryAgain
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from utils import TEST_CHECK_STALE_INTERVAL_S

pytest_simcore_core_services_selection = [
    "rabbit",
]

_RETRY_PARAMS: dict[str, Any] = {
    "reraise": True,
    "wait": wait_fixed(0.1),
    "stop": stop_after_delay(60),
    "retry": retry_if_exception_type((AssertionError, TryAgain)),
}


class _TetingError(Exception):
    pass


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
        raise _TetingError(msg)

    return 42


async def fast_background_task(progress: TaskProgress) -> int:
    """this task does nothing and returns a constant"""
    return 42


async def failing_background_task(progress: TaskProgress):
    """this task does nothing and returns a constant"""
    msg = "failing asap"
    raise _TetingError(msg)


TaskRegistry.register(a_background_task)
TaskRegistry.register(fast_background_task)
TaskRegistry.register(failing_background_task)


@pytest.fixture
def empty_context() -> TaskContext:
    return {}


@pytest.fixture
async def long_running_manager(
    use_in_memory_redis: RedisSettings,
    rabbit_service: RabbitSettings,
    get_long_running_manager: Callable[
        [RedisSettings, RabbitSettings, LRTNamespace | None],
        Awaitable[BaseLongRunningManager],
    ],
) -> BaseLongRunningManager:
    return await get_long_running_manager(
        use_in_memory_redis, rabbit_service, "rabbit-namespace"
    )


@pytest.mark.parametrize("check_task_presence_before", [True, False])
async def test_task_is_auto_removed(
    long_running_manager: BaseLongRunningManager,
    check_task_presence_before: bool,
    empty_context: TaskContext,
):
    task_id = await lrt_api.start_task(
        long_running_manager.rpc_client,
        long_running_manager.lrt_namespace,
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=10 * TEST_CHECK_STALE_INTERVAL_S,
        task_context=empty_context,
    )

    if check_task_presence_before:
        # immediately after starting the task is still there
        task_status = await long_running_manager.tasks_manager.get_task_status(
            task_id, with_task_context=empty_context
        )
        assert task_status

    # wait for task to be automatically removed
    # meaning no calls via the manager methods are received
    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:
            if (
                await long_running_manager.tasks_manager._tasks_data.get_task_data(  # noqa: SLF001
                    task_id
                )
                is not None
            ):
                msg = "wait till no element is found any longer"
                raise TryAgain(msg)

    with pytest.raises(TaskNotFoundError):
        await long_running_manager.tasks_manager.get_task_status(
            task_id, with_task_context=empty_context
        )
    with pytest.raises(TaskNotFoundError):
        await long_running_manager.tasks_manager.get_task_result(
            task_id, with_task_context=empty_context
        )


@pytest.mark.parametrize("wait_multiplier", [1, 2, 3, 4, 5, 6])
async def test_checked_task_is_not_auto_removed(
    long_running_manager: BaseLongRunningManager,
    empty_context: TaskContext,
    wait_multiplier: int,
):
    task_id = await lrt_api.start_task(
        long_running_manager.rpc_client,
        long_running_manager.lrt_namespace,
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=wait_multiplier * TEST_CHECK_STALE_INTERVAL_S,
        task_context=empty_context,
    )
    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:
            status = await long_running_manager.tasks_manager.get_task_status(
                task_id, with_task_context=empty_context
            )
            assert status.done, f"task {task_id} not complete"
    result = await long_running_manager.tasks_manager.get_task_result(
        task_id, with_task_context=empty_context
    )
    assert result


def _get_resutlt(result_field: ResultField) -> Any:
    assert result_field.str_result
    return loads(result_field.str_result)


async def test_fire_and_forget_task_is_not_auto_removed(
    long_running_manager: BaseLongRunningManager, empty_context: TaskContext
):
    task_id = await lrt_api.start_task(
        long_running_manager.rpc_client,
        long_running_manager.lrt_namespace,
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=5 * TEST_CHECK_STALE_INTERVAL_S,
        fire_and_forget=True,
        task_context=empty_context,
    )
    await asyncio.sleep(3 * TEST_CHECK_STALE_INTERVAL_S)
    # the task shall still be present even if we did not check the status before
    status = await long_running_manager.tasks_manager.get_task_status(
        task_id, with_task_context=empty_context
    )
    assert not status.done, "task was removed although it is fire and forget"
    # the task shall finish
    await asyncio.sleep(4 * TEST_CHECK_STALE_INTERVAL_S)
    # get the result
    task_result = await long_running_manager.tasks_manager.get_task_result(
        task_id, with_task_context=empty_context
    )
    assert _get_resutlt(task_result) == 42


async def test_get_result_of_unfinished_task_raises(
    long_running_manager: BaseLongRunningManager, empty_context: TaskContext
):
    task_id = await lrt_api.start_task(
        long_running_manager.rpc_client,
        long_running_manager.lrt_namespace,
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=5 * TEST_CHECK_STALE_INTERVAL_S,
        task_context=empty_context,
    )
    with pytest.raises(TaskNotCompletedError):
        await long_running_manager.tasks_manager.get_task_result(
            task_id, with_task_context=empty_context
        )


async def test_unique_task_already_running(
    long_running_manager: BaseLongRunningManager, empty_context: TaskContext
):
    async def unique_task(progress: TaskProgress):
        _ = progress
        await asyncio.sleep(1)

    TaskRegistry.register(unique_task)

    await lrt_api.start_task(
        long_running_manager.rpc_client,
        long_running_manager.lrt_namespace,
        unique_task.__name__,
        unique=True,
        task_context=empty_context,
    )

    # ensure unique running task regardless of how many times it gets started
    with pytest.raises(TaskAlreadyRunningError) as exec_info:
        await lrt_api.start_task(
            long_running_manager.rpc_client,
            long_running_manager.lrt_namespace,
            unique_task.__name__,
            unique=True,
            task_context=empty_context,
        )
    assert "must be unique, found: " in f"{exec_info.value}"

    TaskRegistry.unregister(unique_task)


async def test_start_multiple_not_unique_tasks(
    long_running_manager: BaseLongRunningManager, empty_context: TaskContext
):
    async def not_unique_task(progress: TaskProgress):
        await asyncio.sleep(1)

    TaskRegistry.register(not_unique_task)

    for _ in range(5):
        await lrt_api.start_task(
            long_running_manager.rpc_client,
            long_running_manager.lrt_namespace,
            not_unique_task.__name__,
            task_context=empty_context,
        )

    TaskRegistry.unregister(not_unique_task)


@pytest.mark.parametrize("is_unique", [True, False])
async def test_get_task_id(
    long_running_manager: BaseLongRunningManager, faker: Faker, is_unique: bool
):
    obj1 = long_running_manager.tasks_manager._get_task_id(  # noqa: SLF001
        faker.word(), is_unique=is_unique
    )
    obj2 = long_running_manager.tasks_manager._get_task_id(  # noqa: SLF001
        faker.word(), is_unique=is_unique
    )
    assert obj1 != obj2


async def test_get_status(
    long_running_manager: BaseLongRunningManager, empty_context: TaskContext
):
    task_id = await lrt_api.start_task(
        long_running_manager.rpc_client,
        long_running_manager.lrt_namespace,
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=10,
        task_context=empty_context,
    )
    task_status = await long_running_manager.tasks_manager.get_task_status(
        task_id, with_task_context=empty_context
    )
    assert isinstance(task_status, TaskStatus)
    assert isinstance(task_status.task_progress.message, ProgressMessage)
    assert task_status.task_progress.percent == 0.0
    assert task_status.done is False
    assert isinstance(task_status.started, datetime)


async def test_get_status_missing(
    long_running_manager: BaseLongRunningManager, empty_context: TaskContext
):
    with pytest.raises(TaskNotFoundError) as exec_info:
        await long_running_manager.tasks_manager.get_task_status(
            "missing_task_id", with_task_context=empty_context
        )
    assert f"{exec_info.value}" == "No task with missing_task_id found"


async def test_get_result(
    long_running_manager: BaseLongRunningManager, empty_context: TaskContext
):
    task_id = await lrt_api.start_task(
        long_running_manager.rpc_client,
        long_running_manager.lrt_namespace,
        fast_background_task.__name__,
        task_context=empty_context,
    )

    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:
            status = await long_running_manager.tasks_manager.get_task_status(
                task_id, with_task_context=empty_context
            )
            assert status.done is True

    result = await long_running_manager.tasks_manager.get_task_result(
        task_id, with_task_context=empty_context
    )
    assert _get_resutlt(result) == 42


async def test_get_result_missing(
    long_running_manager: BaseLongRunningManager, empty_context: TaskContext
):
    with pytest.raises(TaskNotFoundError) as exec_info:
        await long_running_manager.tasks_manager.get_task_result(
            "missing_task_id", with_task_context=empty_context
        )
    assert f"{exec_info.value}" == "No task with missing_task_id found"


async def test_get_result_finished_with_error(
    long_running_manager: BaseLongRunningManager, empty_context: TaskContext
):
    task_id = await lrt_api.start_task(
        long_running_manager.rpc_client,
        long_running_manager.lrt_namespace,
        failing_background_task.__name__,
        task_context=empty_context,
    )
    # wait for result
    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:
            assert (
                await long_running_manager.tasks_manager.get_task_status(
                    task_id, with_task_context=empty_context
                )
            ).done

    result = await long_running_manager.tasks_manager.get_task_result(
        task_id, with_task_context=empty_context
    )
    assert result.str_error is not None  # nosec
    error = loads(result.str_error)
    with pytest.raises(_TetingError, match="failing asap"):
        raise error


async def test_cancel_task_from_different_manager(
    rabbit_service: RabbitSettings,
    use_in_memory_redis: RedisSettings,
    get_long_running_manager: Callable[
        [RedisSettings, RabbitSettings, LRTNamespace | None],
        Awaitable[BaseLongRunningManager],
    ],
    empty_context: TaskContext,
):
    manager_1 = await get_long_running_manager(
        use_in_memory_redis, rabbit_service, "test-namespace"
    )
    manager_2 = await get_long_running_manager(
        use_in_memory_redis, rabbit_service, "test-namespace"
    )
    manager_3 = await get_long_running_manager(
        use_in_memory_redis, rabbit_service, "test-namespace"
    )

    task_id = await lrt_api.start_task(
        manager_1.rpc_client,
        manager_1.lrt_namespace,
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=1,
        task_context=empty_context,
    )

    # wati for task to complete
    for manager in (manager_1, manager_2, manager_3):
        status = await manager.tasks_manager.get_task_status(task_id, empty_context)
        assert status.done is False

    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:
            for manager in (manager_1, manager_2, manager_3):
                status = await manager.tasks_manager.get_task_status(
                    task_id, empty_context
                )
                assert status.done is True

    # check all provide the same result
    for manager in (manager_1, manager_2, manager_3):
        task_result = await manager.tasks_manager.get_task_result(
            task_id, empty_context
        )
        assert _get_resutlt(task_result) == 42


async def test_remove_task(
    long_running_manager: BaseLongRunningManager, empty_context: TaskContext
):
    task_id = await lrt_api.start_task(
        long_running_manager.rpc_client,
        long_running_manager.lrt_namespace,
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=10,
        task_context=empty_context,
    )
    await long_running_manager.tasks_manager.get_task_status(
        task_id, with_task_context=empty_context
    )
    await long_running_manager.tasks_manager.remove_task(
        task_id, with_task_context=empty_context, wait_for_removal=True
    )
    with pytest.raises(TaskNotFoundError):
        await long_running_manager.tasks_manager.get_task_status(
            task_id, with_task_context=empty_context
        )
    with pytest.raises(TaskNotFoundError):
        await long_running_manager.tasks_manager.get_task_result(
            task_id, with_task_context=empty_context
        )


async def test_remove_task_with_task_context(
    long_running_manager: BaseLongRunningManager, empty_context: TaskContext
):
    task_id = await lrt_api.start_task(
        long_running_manager.rpc_client,
        long_running_manager.lrt_namespace,
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=10,
        task_context=empty_context,
    )
    # getting status fails if wrong task context given
    with pytest.raises(TaskNotFoundError):
        await long_running_manager.tasks_manager.get_task_status(
            task_id, with_task_context={"wrong_task_context": 12}
        )
    await long_running_manager.tasks_manager.get_task_status(
        task_id, with_task_context=empty_context
    )

    # removing task fails if wrong task context given
    with pytest.raises(TaskNotFoundError):
        await long_running_manager.tasks_manager.remove_task(
            task_id, with_task_context={"wrong_task_context": 12}, wait_for_removal=True
        )
    await long_running_manager.tasks_manager.remove_task(
        task_id, with_task_context=empty_context, wait_for_removal=True
    )


async def test_remove_unknown_task(
    long_running_manager: BaseLongRunningManager, empty_context: TaskContext
):
    with pytest.raises(TaskNotFoundError):
        await long_running_manager.tasks_manager.remove_task(
            "invalid_id", with_task_context=empty_context, wait_for_removal=True
        )


async def test__cancelled_tasks_worker_equivalent_of_cancellation_from_a_different_process(
    long_running_manager: BaseLongRunningManager, empty_context: TaskContext
):
    task_id = await lrt_api.start_task(
        long_running_manager.rpc_client,
        long_running_manager.lrt_namespace,
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=10,
        task_context=empty_context,
    )
    await long_running_manager.tasks_manager._tasks_data.mark_task_for_removal(  # noqa: SLF001
        task_id, with_task_context=empty_context
    )

    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:  # noqa: SIM117
            with pytest.raises(TaskNotFoundError):
                assert (
                    await long_running_manager.tasks_manager.get_task_status(
                        task_id, empty_context
                    )
                    is None
                )


async def test_list_tasks(
    disable_stale_tasks_monitor: None,
    long_running_manager: BaseLongRunningManager,
    empty_context: TaskContext,
):
    assert (
        await long_running_manager.tasks_manager.list_tasks(
            with_task_context=empty_context
        )
        == []
    )
    # start a bunch of tasks
    NUM_TASKS = 10
    task_ids = []
    for _ in range(NUM_TASKS):
        task_ids.append(  # noqa: PERF401
            await lrt_api.start_task(
                long_running_manager.rpc_client,
                long_running_manager.lrt_namespace,
                a_background_task.__name__,
                raise_when_finished=False,
                total_sleep=10,
                task_context=empty_context,
            )
        )
    assert (
        len(
            await long_running_manager.tasks_manager.list_tasks(
                with_task_context=empty_context
            )
        )
        == NUM_TASKS
    )
    for task_index, task_id in enumerate(task_ids):
        await long_running_manager.tasks_manager.remove_task(
            task_id, with_task_context=empty_context, wait_for_removal=True
        )
        assert len(
            await long_running_manager.tasks_manager.list_tasks(
                with_task_context=empty_context
            )
        ) == NUM_TASKS - (task_index + 1)


async def test_list_tasks_filtering(
    long_running_manager: BaseLongRunningManager, empty_context: TaskContext
):
    await lrt_api.start_task(
        long_running_manager.rpc_client,
        long_running_manager.lrt_namespace,
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=10,
        task_context=empty_context,
    )
    await lrt_api.start_task(
        long_running_manager.rpc_client,
        long_running_manager.lrt_namespace,
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=10,
        task_context={"user_id": 213},
    )
    await lrt_api.start_task(
        long_running_manager.rpc_client,
        long_running_manager.lrt_namespace,
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=10,
        task_context={"user_id": 213, "product": "osparc"},
    )
    assert (
        len(
            await long_running_manager.tasks_manager.list_tasks(
                with_task_context=empty_context
            )
        )
        == 3
    )
    assert (
        len(
            await long_running_manager.tasks_manager.list_tasks(
                with_task_context={"user_id": 213}
            )
        )
        == 1
    )
    assert (
        len(
            await long_running_manager.tasks_manager.list_tasks(
                with_task_context={"user_id": 213, "product": "osparc"}
            )
        )
        == 1
    )
    assert (
        len(
            await long_running_manager.tasks_manager.list_tasks(
                with_task_context={"user_id": 120, "product": "osparc"}
            )
        )
        == 0
    )


async def test_define_task_name(
    long_running_manager: BaseLongRunningManager, faker: Faker
):
    task_name = faker.name()
    task_id = await lrt_api.start_task(
        long_running_manager.rpc_client,
        long_running_manager.lrt_namespace,
        a_background_task.__name__,
        raise_when_finished=False,
        total_sleep=10,
        task_name=task_name,
    )
    assert urllib.parse.quote(task_name, safe="") in task_id


async def test_start_not_registered_task(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    long_running_manager: BaseLongRunningManager,
):
    with pytest.raises(TaskNotRegisteredError):
        await lrt_api.start_task(
            long_running_manager.rpc_client,
            long_running_manager.lrt_namespace,
            "not_registered_task",
        )
