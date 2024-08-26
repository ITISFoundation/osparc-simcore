# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import asyncio
import logging
from collections.abc import AsyncIterable, Awaitable, Callable, Iterable
from datetime import timedelta
from enum import auto
from typing import Any
from unittest.mock import Mock

import pytest
from models_library.utils.enums import StrAutoEnum
from pydantic import NonNegativeInt
from servicelib.deferred_tasks._base_deferred_handler import (
    BaseDeferredHandler,
    DeferredContext,
    StartContext,
)
from servicelib.deferred_tasks._deferred_manager import (
    DeferredManager,
    _FastStreamRabbitQueue,
    _get_queue_from_state,
)
from servicelib.deferred_tasks._models import TaskResultError, TaskUID
from servicelib.deferred_tasks._task_schedule import TaskState
from servicelib.redis import RedisClientSDK
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisDatabase, RedisSettings
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = [
    "rabbit",
    "redis",
]


class MockKeys(StrAutoEnum):
    GET_RETRIES = auto()
    GET_TIMEOUT = auto()
    START_DEFERRED = auto()
    ON_DEFERRED_CREATED = auto()
    RUN_DEFERRED = auto()
    ON_DEFERRED_RESULT = auto()
    ON_FINISHED_WITH_ERROR = auto()


@pytest.fixture
async def redis_client_sdk(
    redis_service: RedisSettings,
) -> AsyncIterable[RedisClientSDK]:
    sdk = RedisClientSDK(redis_service.build_redis_dsn(RedisDatabase.DEFERRED_TASKS))
    await sdk.setup()
    yield sdk
    await sdk.shutdown()


@pytest.fixture
def mocked_deferred_globals() -> dict[str, Any]:
    return {f"global_{i}": Mock for i in range(5)}


@pytest.fixture
async def deferred_manager(
    rabbit_service: RabbitSettings,
    redis_client_sdk: RedisClientSDK,
    mocked_deferred_globals: dict[str, Any],
) -> AsyncIterable[DeferredManager]:
    manager = DeferredManager(
        rabbit_service,
        redis_client_sdk,
        globals_context=mocked_deferred_globals,
        max_workers=10,
    )

    await manager.setup()
    yield manager
    await manager.shutdown()


@pytest.fixture
async def get_mocked_deferred_handler(
    deferred_manager: DeferredManager,
) -> Callable[
    [int, timedelta, Callable[[DeferredContext], Awaitable[Any]]],
    tuple[dict[MockKeys, Mock], type[BaseDeferredHandler]],
]:
    def _(
        retry_count: int,
        timeout: timedelta,
        run: Callable[[DeferredContext], Awaitable[Any]],
    ) -> tuple[dict[MockKeys, Mock], type[BaseDeferredHandler]]:
        mocks: dict[MockKeys, Mock] = {k: Mock() for k in MockKeys}

        class ObservableDeferredHandler(BaseDeferredHandler[Any]):
            @classmethod
            async def get_retries(cls, context: DeferredContext) -> int:
                mocks[MockKeys.GET_RETRIES](retry_count, context)
                return retry_count

            @classmethod
            async def get_timeout(cls, context: DeferredContext) -> timedelta:
                mocks[MockKeys.GET_TIMEOUT](timeout, context)
                return timeout

            @classmethod
            async def start(cls, **kwargs) -> StartContext:
                mocks[MockKeys.START_DEFERRED](kwargs)
                return kwargs

            @classmethod
            async def on_created(
                cls, task_uid: TaskUID, context: DeferredContext
            ) -> None:
                mocks[MockKeys.ON_DEFERRED_CREATED](task_uid, context)

            @classmethod
            async def run(cls, context: DeferredContext) -> Any:
                result = await run(context)
                mocks[MockKeys.RUN_DEFERRED](context)
                return result

            @classmethod
            async def on_result(cls, result: Any, context: DeferredContext) -> None:
                mocks[MockKeys.ON_DEFERRED_RESULT](result, context)

            @classmethod
            async def on_finished_with_error(
                cls, error: TaskResultError, context: DeferredContext
            ) -> None:
                mocks[MockKeys.ON_FINISHED_WITH_ERROR](error, context)

        deferred_manager.patch_based_deferred_handlers()

        return mocks, ObservableDeferredHandler

    return _


@pytest.fixture()
def caplog_debug_level(
    caplog: pytest.LogCaptureFixture,
) -> Iterable[pytest.LogCaptureFixture]:
    with caplog.at_level(logging.DEBUG):
        yield caplog


async def _assert_mock_call(
    mocks: dict[MockKeys, Mock],
    *,
    key: MockKeys,
    count: NonNegativeInt,
    timeout: float = 5,
) -> None:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.01),
        stop=stop_after_delay(timeout),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            assert len(mocks[key].call_args_list) == count


async def _assert_log_message(
    caplog: pytest.LogCaptureFixture,
    *,
    message: str,
    count: NonNegativeInt,
    timeout: float = 5,
) -> None:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.01),
        stop=stop_after_delay(timeout),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            assert caplog.text.count(message) == count


async def test_rabbit_resources_are_prefixed_with_instancing_module_name(
    deferred_manager: DeferredManager,
):
    # pylint:disable=protected-access
    assert deferred_manager._global_resources_prefix == __name__  # noqa: SLF001


@pytest.mark.parametrize(
    "run_return", [{}, None, 1, 1.34, [], [12, 35, 7, "str", 455.66]]
)
async def test_deferred_manager_result_ok(
    get_mocked_deferred_handler: Callable[
        [int, timedelta, Callable[[DeferredContext], Awaitable[Any]]],
        tuple[dict[MockKeys, Mock], type[BaseDeferredHandler]],
    ],
    mocked_deferred_globals: dict[str, Any],
    run_return: Any,
):
    async def _run_ok(_: DeferredContext) -> Any:
        return run_return

    retry_count = 1
    timeout = timedelta(seconds=1)
    mocks, mocked_deferred_handler = get_mocked_deferred_handler(
        retry_count, timeout, _run_ok
    )

    start_kwargs = {f"start_with{i}": f"par-{i}" for i in range(6)}
    await mocked_deferred_handler.start(**start_kwargs)

    context = {**mocked_deferred_globals, **start_kwargs}

    await _assert_mock_call(mocks, key=MockKeys.GET_RETRIES, count=1)
    mocks[MockKeys.GET_RETRIES].assert_called_with(retry_count, context)

    await _assert_mock_call(mocks, key=MockKeys.GET_TIMEOUT, count=1)
    mocks[MockKeys.GET_TIMEOUT].assert_called_with(timeout, context)

    await _assert_mock_call(mocks, key=MockKeys.START_DEFERRED, count=1)
    mocks[MockKeys.START_DEFERRED].assert_called_with(start_kwargs)

    await _assert_mock_call(mocks, key=MockKeys.ON_DEFERRED_CREATED, count=1)
    assert TaskUID(mocks[MockKeys.ON_DEFERRED_CREATED].call_args_list[0].args[0])

    await _assert_mock_call(mocks, key=MockKeys.RUN_DEFERRED, count=1)
    mocks[MockKeys.RUN_DEFERRED].assert_called_once_with(context)

    await _assert_mock_call(mocks, key=MockKeys.ON_DEFERRED_RESULT, count=1)
    mocks[MockKeys.ON_DEFERRED_RESULT].assert_called_once_with(run_return, context)

    await _assert_mock_call(mocks, key=MockKeys.ON_FINISHED_WITH_ERROR, count=0)


@pytest.mark.parametrize("retry_count", [1, 5])
async def test_deferred_manager_raised_error(
    get_mocked_deferred_handler: Callable[
        [int, timedelta, Callable[[DeferredContext], Awaitable[Any]]],
        tuple[dict[MockKeys, Mock], type[BaseDeferredHandler]],
    ],
    mocked_deferred_globals: dict[str, Any],
    caplog_debug_level: pytest.LogCaptureFixture,
    retry_count: int,
):
    caplog_debug_level.clear()

    expected_error_message = (
        "This is an expected error that was raised and should be found in the logs"
    )

    async def _run_raises(_: DeferredContext) -> None:
        raise RuntimeError(expected_error_message)

    mocks, mocked_deferred_handler = get_mocked_deferred_handler(
        retry_count, timedelta(seconds=1), _run_raises
    )

    await mocked_deferred_handler.start()

    await _assert_mock_call(mocks, key=MockKeys.START_DEFERRED, count=1)
    mocks[MockKeys.START_DEFERRED].assert_called_once_with({})

    await _assert_mock_call(mocks, key=MockKeys.ON_DEFERRED_CREATED, count=1)
    task_uid = TaskUID(mocks[MockKeys.ON_DEFERRED_CREATED].call_args_list[0].args[0])

    await _assert_mock_call(mocks, key=MockKeys.ON_FINISHED_WITH_ERROR, count=1)
    result, received_globals = (
        mocks[MockKeys.ON_FINISHED_WITH_ERROR].call_args_list[0].args
    )
    assert isinstance(result, TaskResultError)
    assert mocked_deferred_globals == received_globals
    if retry_count > 1:
        await _assert_log_message(
            caplog_debug_level,
            message=f"Schedule retry attempt for task_uid '{task_uid}'",
            count=retry_count,
        )

    await _assert_mock_call(mocks, key=MockKeys.RUN_DEFERRED, count=0)
    await _assert_mock_call(mocks, key=MockKeys.ON_DEFERRED_RESULT, count=0)

    await _assert_log_message(
        caplog_debug_level,
        message=f"Finished task_uid '{task_uid}' with error",
        count=1,
    )
    assert expected_error_message in caplog_debug_level.text


@pytest.mark.parametrize("retry_count", [1, 5])
async def test_deferred_manager_cancelled(
    get_mocked_deferred_handler: Callable[
        [int, timedelta, Callable[[DeferredContext], Awaitable[Any]]],
        tuple[dict[MockKeys, Mock], type[BaseDeferredHandler]],
    ],
    caplog_debug_level: pytest.LogCaptureFixture,
    retry_count: int,
):
    caplog_debug_level.clear()

    async def _run_to_cancel(_: DeferredContext) -> None:
        await asyncio.sleep(1e6)

    mocks, mocked_deferred_handler = get_mocked_deferred_handler(
        retry_count, timedelta(seconds=10), _run_to_cancel
    )

    await mocked_deferred_handler.start()

    await _assert_mock_call(mocks, key=MockKeys.START_DEFERRED, count=1)
    mocks[MockKeys.START_DEFERRED].assert_called_once_with({})

    await _assert_mock_call(mocks, key=MockKeys.ON_DEFERRED_CREATED, count=1)
    task_uid = TaskUID(mocks[MockKeys.ON_DEFERRED_CREATED].call_args_list[0].args[0])

    await mocked_deferred_handler.cancel(task_uid)

    await _assert_mock_call(mocks, key=MockKeys.ON_FINISHED_WITH_ERROR, count=0)

    assert (
        caplog_debug_level.text.count(
            f"Schedule retry attempt for task_uid '{task_uid}'"
        )
        == 0
    )

    await _assert_mock_call(mocks, key=MockKeys.RUN_DEFERRED, count=0)
    await _assert_mock_call(mocks, key=MockKeys.ON_DEFERRED_RESULT, count=0)

    await _assert_log_message(
        caplog_debug_level,
        message=f"Found and cancelled run for '{task_uid}'",
        count=1,
    )


@pytest.mark.parametrize("fail", [True, False])
async def test_deferred_manager_task_is_present(
    get_mocked_deferred_handler: Callable[
        [int, timedelta, Callable[[DeferredContext], Awaitable[Any]]],
        tuple[dict[MockKeys, Mock], type[BaseDeferredHandler]],
    ],
    fail: bool,
):
    total_wait_time = 0.5

    async def _run_for_short_period(context: DeferredContext) -> None:
        await asyncio.sleep(total_wait_time)
        if context["fail"]:
            msg = "Failing at the end of sleeping as requested"
            raise RuntimeError(msg)

    mocks, mocked_deferred_handler = get_mocked_deferred_handler(
        0, timedelta(seconds=10), _run_for_short_period
    )

    await mocked_deferred_handler.start(fail=fail)

    await _assert_mock_call(mocks, key=MockKeys.START_DEFERRED, count=1)
    mocks[MockKeys.START_DEFERRED].assert_called_once_with({"fail": fail})

    await _assert_mock_call(mocks, key=MockKeys.ON_DEFERRED_CREATED, count=1)
    task_uid = TaskUID(mocks[MockKeys.ON_DEFERRED_CREATED].call_args_list[0].args[0])

    assert await mocked_deferred_handler.is_present(task_uid) is True

    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.01),
        stop=stop_after_delay(total_wait_time * 2),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            assert await mocked_deferred_handler.is_present(task_uid) is False

    if fail:
        await _assert_mock_call(mocks, key=MockKeys.ON_FINISHED_WITH_ERROR, count=1)
        await _assert_mock_call(mocks, key=MockKeys.ON_DEFERRED_RESULT, count=0)
    else:
        await _assert_mock_call(mocks, key=MockKeys.ON_DEFERRED_RESULT, count=1)
        await _assert_mock_call(mocks, key=MockKeys.ON_FINISHED_WITH_ERROR, count=0)


@pytest.mark.parametrize("tasks_to_start", [100])
async def test_deferred_manager_start_parallelized(
    get_mocked_deferred_handler: Callable[
        [int, timedelta, Callable[[DeferredContext], Awaitable[Any]]],
        tuple[dict[MockKeys, Mock], type[BaseDeferredHandler]],
    ],
    mocked_deferred_globals: dict[str, Any],
    caplog_debug_level: pytest.LogCaptureFixture,
    tasks_to_start: NonNegativeInt,
):
    caplog_debug_level.clear()

    async def _run_ok(_: DeferredContext) -> None:
        await asyncio.sleep(0.1)

    mocks, mocked_deferred_handler = get_mocked_deferred_handler(
        3, timedelta(seconds=1), _run_ok
    )

    await asyncio.gather(
        *[mocked_deferred_handler.start() for _ in range(tasks_to_start)]
    )

    await _assert_mock_call(
        mocks, key=MockKeys.ON_DEFERRED_RESULT, count=tasks_to_start, timeout=10
    )
    for entry in mocks[MockKeys.ON_DEFERRED_RESULT].call_args_list:
        assert entry.args == (None, mocked_deferred_globals)

    await _assert_mock_call(mocks, key=MockKeys.ON_FINISHED_WITH_ERROR, count=0)
    await _assert_log_message(
        caplog_debug_level, message="Schedule retry attempt for task_uid ", count=0
    )
    await _assert_log_message(
        caplog_debug_level, message="Found and cancelled run for '", count=0
    )


async def test_deferred_manager_code_times_out(
    get_mocked_deferred_handler: Callable[
        [int, timedelta, Callable[[DeferredContext], Awaitable[Any]]],
        tuple[dict[MockKeys, Mock], type[BaseDeferredHandler]],
    ]
):
    async def _run_that_times_out(_: DeferredContext) -> None:
        await asyncio.sleep(1e6)

    mocks, mocked_deferred_handler = get_mocked_deferred_handler(
        1, timedelta(seconds=0.5), _run_that_times_out
    )

    await mocked_deferred_handler.start()

    await _assert_mock_call(mocks, key=MockKeys.START_DEFERRED, count=1)
    mocks[MockKeys.START_DEFERRED].assert_called_once_with({})

    await _assert_mock_call(mocks, key=MockKeys.ON_DEFERRED_CREATED, count=1)
    assert TaskUID(mocks[MockKeys.ON_DEFERRED_CREATED].call_args_list[0].args[0])

    await _assert_mock_call(mocks, key=MockKeys.ON_FINISHED_WITH_ERROR, count=1)
    for entry in mocks[MockKeys.ON_FINISHED_WITH_ERROR].call_args_list:
        assert "builtins.TimeoutError" in entry.args[0].error

    await _assert_mock_call(mocks, key=MockKeys.RUN_DEFERRED, count=0)
    await _assert_mock_call(mocks, key=MockKeys.ON_DEFERRED_RESULT, count=0)


def test_enums_have_same_entries():
    assert len(TaskState) == len(_FastStreamRabbitQueue)


@pytest.mark.parametrize(
    "state, queue",
    [
        (TaskState.SCHEDULED, _FastStreamRabbitQueue.SCHEDULED),
        (TaskState.SUBMIT_TASK, _FastStreamRabbitQueue.SUBMIT_TASK),
        (TaskState.WORKER, _FastStreamRabbitQueue.WORKER),
        (TaskState.ERROR_RESULT, _FastStreamRabbitQueue.ERROR_RESULT),
        (TaskState.DEFERRED_RESULT, _FastStreamRabbitQueue.DEFERRED_RESULT),
        (TaskState.FINISHED_WITH_ERROR, _FastStreamRabbitQueue.FINISHED_WITH_ERROR),
        (TaskState.MANUALLY_CANCELLED, _FastStreamRabbitQueue.MANUALLY_CANCELLED),
    ],
)
def test__get_queue_from_state(state: TaskState, queue: _FastStreamRabbitQueue):
    assert _get_queue_from_state(state) == queue
