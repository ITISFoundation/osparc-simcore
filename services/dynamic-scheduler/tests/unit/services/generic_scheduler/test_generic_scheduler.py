# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import asyncio
import secrets
from collections.abc import AsyncIterable, AsyncIterator, Callable, Iterable
from contextlib import (
    AbstractAsyncContextManager,
    asynccontextmanager,
)
from datetime import timedelta
from enum import Enum
from multiprocessing import Process, Queue
from typing import Any, Final

import pytest
from asgi_lifespan import LifespanManager
from common_library.async_tools import cancel_wait_task
from fastapi import FastAPI
from pydantic import NonNegativeFloat, NonNegativeInt
from pytest_simcore.helpers.paused_container import pause_rabbit, pause_redis
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.deferred_tasks import DeferredContext
from servicelib.rabbitmq import RabbitMQClient
from servicelib.redis._client import RedisClientSDK
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisDatabase, RedisSettings
from simcore_service_dynamic_scheduler.core.application import create_app
from simcore_service_dynamic_scheduler.services.generic_scheduler import (
    BaseStep,
    Operation,
    OperationName,
    OperationToStart,
    ParallelStepGroup,
    ProvidedOperationContext,
    RequiredOperationContext,
    SingleStepGroup,
    register_to_start_after_on_created_completed,
    register_to_start_after_on_undo_completed,
    start_operation,
)
from utils import (
    BaseExpectedStepOrder,
    CreateRandom,
    CreateSequence,
    UndoSequence,
    ensure_expected_order,
    ensure_keys_in_store,
)

pytest_simcore_core_services_selection = [
    "rabbit",
    "redis",
]
pytest_simcore_ops_services_selection = [
    "redis-commander",
]


_OPERATION_MIN_RUNTIME: Final[timedelta] = timedelta(seconds=2)
_OPERATION_STEPS_COUNT: Final[NonNegativeInt] = 10
_STEP_SLEEP_DURATION: Final[timedelta] = _OPERATION_MIN_RUNTIME / _OPERATION_STEPS_COUNT
_RETRY_ATTEMPTS: Final[NonNegativeInt] = 10


def _get_random_interruption_duration() -> NonNegativeFloat:
    random_duration = secrets.SystemRandom().uniform(
        0.1, _OPERATION_MIN_RUNTIME.total_seconds()
    )
    print(f"⏳ Waiting {random_duration:.1f} seconds before interrupting...")
    return random_duration


@pytest.fixture
def app_environment(
    disable_postgres_lifespan: None,
    disable_service_tracker_lifespan: None,
    disable_notifier_lifespan: None,
    disable_status_monitor_lifespan: None,
    app_environment: EnvVarsDict,
    rabbit_service: RabbitSettings,
    redis_service: RedisSettings,
    remove_redis_data: None,
) -> EnvVarsDict:
    return app_environment


@pytest.fixture
async def rabbit_client(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
) -> RabbitMQClient:
    return create_rabbitmq_client("pinger")


@pytest.fixture
async def redis_client_sdk(
    redis_service: RedisSettings,
) -> RedisClientSDK:
    return RedisClientSDK(
        redis_service.build_redis_dsn(RedisDatabase.DYNAMIC_SERVICES),
        client_name="test-client",
    )


class _AsyncMultiprocessingQueue:
    def __init__(self) -> None:
        self._queue = Queue()

    async def get(self) -> Any:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._queue.get)

    async def put(self, item: Any) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._queue.put, item)


@pytest.fixture
async def multiprocessing_queue() -> _AsyncMultiprocessingQueue:
    return _AsyncMultiprocessingQueue()


class _QueuePoller:
    def __init__(self, queue: _AsyncMultiprocessingQueue) -> None:
        self._events: list[tuple[str, str]] = []
        self.queue = queue

    @property
    def events(self) -> list[tuple[str, str]]:
        return self._events

    async def poll_worker(self) -> None:
        while True:
            event = await self.queue.get()
            self._events.append(event)
            if event is None:
                break

    async def reset(self) -> None:
        self._events.clear()


@pytest.fixture
async def queue_poller(
    multiprocessing_queue: _AsyncMultiprocessingQueue,
) -> AsyncIterable[_QueuePoller]:
    poller = _QueuePoller(multiprocessing_queue)
    task = asyncio.create_task(poller.poll_worker(), name="queue-poller")

    yield poller

    await multiprocessing_queue.put(None)  # unblock queue if needed
    await cancel_wait_task(task)


@asynccontextmanager
async def _get_app(
    multiprocessing_queue: _AsyncMultiprocessingQueue,
) -> AsyncIterator[FastAPI]:
    app = create_app()
    app.state.multiprocessing_queue = multiprocessing_queue
    async with LifespanManager(app):
        yield app


class _ProcessManager:
    def __init__(self, multiprocessing_queue: _AsyncMultiprocessingQueue) -> None:
        self.multiprocessing_queue = multiprocessing_queue
        self.process: Process | None = None

    async def _async_worker(self, operation_name: OperationName) -> None:
        async with _get_app(self.multiprocessing_queue) as app:
            await start_operation(app, operation_name, {})
            while True:  # noqa: ASYNC110
                await asyncio.sleep(1)

    def _worker(self, operation_name: OperationName) -> None:
        asyncio.run(self._async_worker(operation_name))

    def start(self, operation_name: OperationName) -> None:
        if self.process:
            msg = "Process already started"
            raise RuntimeError(msg)

        self.process = Process(target=self._worker, args=(operation_name,), daemon=True)
        self.process.start()

    def kill(self) -> None:
        if self.process is None:
            return

        self.process.terminate()
        self.process.join()
        self.process = None


@pytest.fixture
def process_manager(
    multiprocessing_queue: _AsyncMultiprocessingQueue,
) -> Iterable[_ProcessManager]:
    process_manager = _ProcessManager(multiprocessing_queue)

    yield process_manager
    process_manager.kill()


@pytest.fixture
def operation_name() -> OperationName:
    return "test-op"


class _InterruptionType(str, Enum):
    REDIS = "redis"
    RABBIT = "rabbit"
    DYNAMIC_SCHEDULER = "dynamic-scheduler"


_CREATED: Final[str] = "create"
_UNDONE: Final[str] = "undo"

_CTX_VALUE: Final[str] = "a_value"


_STEPS_CALL_ORDER: list[tuple[str, str]] = []


@pytest.fixture
def steps_call_order() -> Iterable[list[tuple[str, str]]]:
    _STEPS_CALL_ORDER.clear()
    yield _STEPS_CALL_ORDER
    _STEPS_CALL_ORDER.clear()


class _BS(BaseStep):
    @classmethod
    async def get_create_retries(cls, context: DeferredContext) -> int:
        _ = context
        return _RETRY_ATTEMPTS

    @classmethod
    async def get_create_wait_between_attempts(
        cls, context: DeferredContext
    ) -> timedelta:
        _ = context
        return _STEP_SLEEP_DURATION

    @classmethod
    async def create(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        if hasattr(app.state, "multiprocessing_queue"):
            multiprocessing_queue: _AsyncMultiprocessingQueue = (
                app.state.multiprocessing_queue
            )
            await multiprocessing_queue.put((cls.__name__, _CREATED))
        _STEPS_CALL_ORDER.append((cls.__name__, _CREATED))

        return {
            **required_context,
            **{k: _CTX_VALUE for k in cls.get_create_provides_context_keys()},
        }

    @classmethod
    async def undo(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        if hasattr(app.state, "multiprocessing_queue"):
            multiprocessing_queue: _AsyncMultiprocessingQueue = (
                app.state.multiprocessing_queue
            )
            await multiprocessing_queue.put((cls.__name__, _UNDONE))
        _STEPS_CALL_ORDER.append((cls.__name__, _UNDONE))

        return {
            **required_context,
            **{k: _CTX_VALUE for k in cls.get_undo_provides_context_keys()},
        }


class _S1(_BS): ...


class _S2(_BS): ...


class _S3(_BS): ...


class _ShortSleep(_BS):
    @classmethod
    async def create(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        result = await super().create(app, required_context)
        # if sleeps more than this it will timeout
        max_allowed_sleep = _STEP_SLEEP_DURATION.total_seconds() * 0.8
        await asyncio.sleep(max_allowed_sleep)
        return result


class _ShortSleepThenUndo(_BS):
    @classmethod
    async def get_create_retries(cls, context: DeferredContext) -> int:
        _ = context
        return 0

    @classmethod
    async def create(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        await super().create(app, required_context)
        # if sleeps more than this it will timeout
        max_allowed_sleep = _STEP_SLEEP_DURATION.total_seconds() * 0.8
        await asyncio.sleep(max_allowed_sleep)
        msg = "Simulated error"
        raise RuntimeError(msg)


@pytest.mark.parametrize(
    "operation, expected_order",
    [
        pytest.param(
            Operation(
                SingleStepGroup(_S1),
            ),
            [
                CreateSequence(_S1),
            ],
            id="s1",
        ),
        pytest.param(
            Operation(
                ParallelStepGroup(_S1, _S2, _S3),
            ),
            [
                CreateRandom(_S1, _S2, _S3),
            ],
            id="p3",
        ),
    ],
)
@pytest.mark.parametrize("interruption_type", list(_InterruptionType))
async def test_can_recover_from_interruption(
    app_environment: EnvVarsDict,
    interruption_type: _InterruptionType,
    rabbit_client: RabbitMQClient,
    redis_client_sdk: RedisClientSDK,
    register_operation: Callable[[OperationName, Operation], None],
    paused_container: Callable[[str], AbstractAsyncContextManager[None]],
    operation: Operation,
    queue_poller: _QueuePoller,
    process_manager: _ProcessManager,
    expected_order: list[BaseExpectedStepOrder],
    operation_name: OperationName,
) -> None:
    register_operation(operation_name, operation)
    process_manager.start(operation_name)

    match interruption_type:
        case _InterruptionType.REDIS:
            print(f"[{interruption_type}]: will pause ⚙️")
            async with pause_rabbit(paused_container, rabbit_client):
                print(f"[{interruption_type}]: paused ⏸️")

                await asyncio.sleep(_get_random_interruption_duration())
            print(f"[{interruption_type}]: unpaused ⏯️")
        case _InterruptionType.RABBIT:
            print(f"[{interruption_type}]: will pause ⚙️")
            async with pause_redis(paused_container, redis_client_sdk):
                print(f"[{interruption_type}]: paused ⏸️")

                await asyncio.sleep(_get_random_interruption_duration())
            print(f"[{interruption_type}]: unpaused ⏯️")
        case _InterruptionType.DYNAMIC_SCHEDULER:
            print(f"[{interruption_type}]: will pause ⚙️")
            process_manager.kill()
            print(f"[{interruption_type}]: paused ⏸️")

            await asyncio.sleep(_get_random_interruption_duration())
            process_manager.start(operation_name)
            print(f"[{interruption_type}]: unpaused ⏯️")
        case _:
            msg = f"Unhandled interruption_type={interruption_type}"
            raise RuntimeError(msg)

    await ensure_expected_order(queue_poller.events, expected_order)


@pytest.mark.parametrize("register_at_creation", [True, False])
@pytest.mark.parametrize(
    "is_creating, initial_op, after_op, expected_order",
    [
        pytest.param(
            True,
            Operation(SingleStepGroup(_ShortSleep)),
            Operation(SingleStepGroup(_S2)),
            [
                CreateSequence(_ShortSleep),
                CreateSequence(_S2),
            ],
        ),
        pytest.param(
            False,
            Operation(SingleStepGroup(_ShortSleepThenUndo)),
            Operation(SingleStepGroup(_S2)),
            [
                CreateSequence(_ShortSleepThenUndo),
                UndoSequence(_ShortSleepThenUndo),
                CreateSequence(_S2),
            ],
        ),
    ],
)
async def test_create_undo_order(
    app: FastAPI,
    preserve_caplog_for_async_logging: None,
    steps_call_order: list[tuple[str, str]],
    register_operation: Callable[[OperationName, Operation], None],
    register_at_creation: bool,
    is_creating: bool,
    initial_op: Operation,
    after_op: Operation,
    expected_order: list[BaseExpectedStepOrder],
):
    initial_op_name: OperationName = "intial"
    after_op_name: OperationName = "after"

    register_operation(initial_op_name, initial_op)
    register_operation(after_op_name, after_op)

    if is_creating:
        on_create_completed = (
            OperationToStart(operation_name=after_op_name, initial_context={})
            if register_at_creation
            else None
        )
        on_undo_completed = None
    else:
        on_create_completed = None
        on_undo_completed = (
            OperationToStart(operation_name=after_op_name, initial_context={})
            if register_at_creation
            else None
        )

    schedule_id = await start_operation(
        app,
        initial_op_name,
        {},
        on_create_completed=on_create_completed,
        on_undo_completed=on_undo_completed,
    )

    if not register_at_creation:
        if is_creating:
            await register_to_start_after_on_created_completed(
                app,
                schedule_id,
                to_start=OperationToStart(
                    operation_name=after_op_name, initial_context={}
                ),
            )
        else:
            await register_to_start_after_on_undo_completed(
                app,
                schedule_id,
                to_start=OperationToStart(
                    operation_name=after_op_name, initial_context={}
                ),
            )

    await ensure_expected_order(steps_call_order, expected_order)
    await ensure_keys_in_store(app, expected_keys=set())
