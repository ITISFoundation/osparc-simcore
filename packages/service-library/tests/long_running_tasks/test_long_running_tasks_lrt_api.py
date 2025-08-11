# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
import secrets
from collections.abc import Awaitable, Callable
from typing import Any, Final

import pytest
from models_library.api_schemas_long_running_tasks.base import TaskProgress
from pydantic import NonNegativeInt
from pytest_mock import MockerFixture
from servicelib.long_running_tasks import lrt_api
from servicelib.long_running_tasks._rabbit.lrt_client import RabbitNamespace
from servicelib.long_running_tasks.errors import TaskNotFoundError
from servicelib.long_running_tasks.models import TaskContext
from servicelib.long_running_tasks.task import (
    RedisNamespace,
    TaskId,
    TaskRegistry,
    TasksManager,
)
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from tenacity import (
    AsyncRetrying,
    TryAgain,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)
from utils import NoWebAppLongRunningManager

pytest_simcore_core_services_selection = [
    "rabbit",
]

_RETRY_PARAMS: dict[str, Any] = {
    "reraise": True,
    "wait": wait_fixed(0.1),
    "stop": stop_after_delay(60),
    "retry": retry_if_exception_type((AssertionError, TryAgain)),
}


async def _task_echo_input(progress: TaskProgress, to_return: Any) -> Any:
    return to_return


async def _task_always_raise(progress: TaskProgress) -> None:
    msg = "This task always raises an error"
    raise RuntimeError(msg)


async def _task_takes_too_long(progress: TaskProgress) -> None:
    # Simulate a long-running task that is taking too much time
    await asyncio.sleep(1e9)


TaskRegistry.register(_task_echo_input)
TaskRegistry.register(_task_always_raise)
TaskRegistry.register(_task_takes_too_long)


@pytest.fixture
def managers_count() -> NonNegativeInt:
    return 5


@pytest.fixture
def disable_stale_tasks_monitor(mocker: MockerFixture) -> None:
    # no need to autoremove stale tasks in these tests
    async def _to_replace(self: TasksManager) -> None:
        self._started_event_task_stale_tasks_monitor.set()

    mocker.patch.object(TasksManager, "_stale_tasks_monitor", _to_replace)


@pytest.fixture
async def long_running_managers(
    disable_stale_tasks_monitor: None,
    managers_count: NonNegativeInt,
    use_in_memory_redis: RedisSettings,
    rabbit_service: RabbitSettings,
    get_long_running_manager: Callable[
        [RedisSettings, RedisNamespace | None, RabbitSettings, RabbitNamespace],
        Awaitable[NoWebAppLongRunningManager],
    ],
) -> list[NoWebAppLongRunningManager]:
    maanagers: list[NoWebAppLongRunningManager] = []
    for _ in range(managers_count):
        long_running_manager = await get_long_running_manager(
            use_in_memory_redis, "same-service", rabbit_service, "some-service"
        )
        maanagers.append(long_running_manager)

    return maanagers


def _get_task_manager(
    long_running_managers: list[NoWebAppLongRunningManager],
) -> NoWebAppLongRunningManager:
    return secrets.choice(long_running_managers)


async def _assert_task_status(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    long_running_manager: NoWebAppLongRunningManager,
    task_id: TaskId,
    *,
    is_done: bool
) -> None:
    result = await lrt_api.get_task_status(
        rabbitmq_rpc_client, long_running_manager, TaskContext(), task_id
    )
    assert result.done is is_done


async def _assert_task_status_on_random_manager(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    long_running_managers: list[NoWebAppLongRunningManager],
    task_ids: list[TaskId],
    *,
    is_done: bool = True
) -> None:
    for task_id in task_ids:
        result = await lrt_api.get_task_status(
            rabbitmq_rpc_client,
            _get_task_manager(long_running_managers),
            TaskContext(),
            task_id,
        )
        assert result.done is is_done


async def _assert_task_status_done_on_all_managers(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    long_running_managers: list[NoWebAppLongRunningManager],
    task_id: TaskId,
    *,
    is_done: bool = True
) -> None:
    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:
            await _assert_task_status(
                rabbitmq_rpc_client,
                _get_task_manager(long_running_managers),
                task_id,
                is_done=is_done,
            )

    # check can do this form any task manager
    for manager in long_running_managers:
        await _assert_task_status(
            rabbitmq_rpc_client, manager, task_id, is_done=is_done
        )


async def _assert_list_tasks_from_all_managers(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    long_running_managers: list[NoWebAppLongRunningManager],
    task_context: TaskContext,
    task_count: int,
) -> None:
    for manager in long_running_managers:
        tasks = await lrt_api.list_tasks(rabbitmq_rpc_client, manager, task_context)
        assert len(tasks) == task_count


async def _assert_task_is_no_longer_present(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    long_running_managers: list[NoWebAppLongRunningManager],
    task_context: TaskContext,
    task_id: TaskId,
) -> None:
    with pytest.raises(TaskNotFoundError):
        await lrt_api.get_task_status(
            rabbitmq_rpc_client,
            _get_task_manager(long_running_managers),
            task_context,
            task_id,
        )


_TASK_CONTEXT: Final[list[TaskContext | None]] = [{"a": "context"}, None]
_IS_UNIQUE: Final[list[bool]] = [False, True]
_TASK_COUNT: Final[list[int]] = [5]


@pytest.mark.parametrize("task_count", _TASK_COUNT)
@pytest.mark.parametrize("task_context", _TASK_CONTEXT)
@pytest.mark.parametrize("is_unique", _IS_UNIQUE)
@pytest.mark.parametrize("to_return", [{"key": "value"}])
async def test_workflow_with_result(
    long_running_managers: list[NoWebAppLongRunningManager],
    rabbitmq_rpc_client: RabbitMQRPCClient,
    task_count: int,
    is_unique: bool,
    task_context: TaskContext | None,
    to_return: Any,
):
    saved_context = task_context or {}
    task_count = 1 if is_unique else task_count

    task_ids: list[TaskId] = []
    for _ in range(task_count):
        task_id = await lrt_api.start_task(
            rabbitmq_rpc_client,
            _get_task_manager(long_running_managers),
            _task_echo_input.__name__,
            unique=is_unique,
            task_name=None,
            task_context=task_context,
            fire_and_forget=False,
            to_return=to_return,
        )
        task_ids.append(task_id)

    for task_id in task_ids:
        await _assert_task_status_done_on_all_managers(
            rabbitmq_rpc_client, long_running_managers, task_id
        )

    await _assert_list_tasks_from_all_managers(
        rabbitmq_rpc_client, long_running_managers, saved_context, task_count=task_count
    )

    # avoids tasks getting garbage collected
    await _assert_task_status_on_random_manager(
        rabbitmq_rpc_client, long_running_managers, task_ids, is_done=True
    )

    for task_id in task_ids:
        result = await lrt_api.get_task_result(
            rabbitmq_rpc_client,
            _get_task_manager(long_running_managers),
            saved_context,
            task_id,
        )
        assert result == to_return

        await _assert_task_is_no_longer_present(
            rabbitmq_rpc_client, long_running_managers, saved_context, task_id
        )


@pytest.mark.parametrize("task_count", _TASK_COUNT)
@pytest.mark.parametrize("task_context", _TASK_CONTEXT)
@pytest.mark.parametrize("is_unique", _IS_UNIQUE)
async def test_workflow_raises_error(
    long_running_managers: list[NoWebAppLongRunningManager],
    rabbitmq_rpc_client: RabbitMQRPCClient,
    task_count: int,
    is_unique: bool,
    task_context: TaskContext | None,
):
    saved_context = task_context or {}
    task_count = 1 if is_unique else task_count

    task_ids: list[TaskId] = []
    for _ in range(task_count):
        task_id = await lrt_api.start_task(
            rabbitmq_rpc_client,
            _get_task_manager(long_running_managers),
            _task_always_raise.__name__,
            unique=is_unique,
            task_name=None,
            task_context=task_context,
            fire_and_forget=False,
        )
        task_ids.append(task_id)

    for task_id in task_ids:
        await _assert_task_status_done_on_all_managers(
            rabbitmq_rpc_client, long_running_managers, task_id
        )

    await _assert_list_tasks_from_all_managers(
        rabbitmq_rpc_client, long_running_managers, saved_context, task_count=task_count
    )

    # avoids tasks getting garbage collected
    await _assert_task_status_on_random_manager(
        rabbitmq_rpc_client, long_running_managers, task_ids, is_done=True
    )

    for task_id in task_ids:
        with pytest.raises(RuntimeError, match="This task always raises an error"):
            await lrt_api.get_task_result(
                rabbitmq_rpc_client,
                _get_task_manager(long_running_managers),
                saved_context,
                task_id,
            )

        await _assert_task_is_no_longer_present(
            rabbitmq_rpc_client, long_running_managers, saved_context, task_id
        )


@pytest.mark.parametrize("task_context", _TASK_CONTEXT)
@pytest.mark.parametrize("is_unique", _IS_UNIQUE)
async def test_remove_task(
    long_running_managers: list[NoWebAppLongRunningManager],
    rabbitmq_rpc_client: RabbitMQRPCClient,
    is_unique: bool,
    task_context: TaskContext | None,
):
    task_id = await lrt_api.start_task(
        rabbitmq_rpc_client,
        _get_task_manager(long_running_managers),
        _task_takes_too_long.__name__,
        unique=is_unique,
        task_name=None,
        task_context=task_context,
        fire_and_forget=False,
    )
    saved_context = task_context or {}

    await _assert_task_status_done_on_all_managers(
        rabbitmq_rpc_client, long_running_managers, task_id, is_done=False
    )

    await lrt_api.remove_task(
        rabbitmq_rpc_client,
        _get_task_manager(long_running_managers),
        saved_context,
        task_id,
    )

    await _assert_task_is_no_longer_present(
        rabbitmq_rpc_client, long_running_managers, saved_context, task_id
    )
