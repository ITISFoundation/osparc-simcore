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
from pytest_simcore.helpers.docker import ServiceManager
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
    ParallelStepGroup,
    ProvidedOperationContext,
    RequiredOperationContext,
    SingleStepGroup,
    start_operation,
)
from utils import (
    BaseExpectedStepOrder,
    CreateRandom,
    CreateSequence,
    ensure_expected_order,
)

pytest_simcore_core_services_selection = [
    "rabbit",
    "redis",
]
pytest_simcore_ops_services_selection = [
    "redis-commander",
]


_OPERATION_MIN_RUNTIME: Final[timedelta] = timedelta(seconds=2)
_OPRATION_STEPS_COUNT: Final[NonNegativeInt] = 10
_STEP_SLEEP_DURATION: Final[timedelta] = _OPERATION_MIN_RUNTIME / _OPRATION_STEPS_COUNT


def _get_random_duration_before_interrupting() -> NonNegativeFloat:
    ranom_duration = secrets.SystemRandom().uniform(
        0.1, _OPERATION_MIN_RUNTIME.total_seconds()
    )
    print(f"⏳ Waiting {ranom_duration:.1f} seconds before interrupting...")
    return ranom_duration


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


class _InterruptionType(str, Enum):
    REDIS = "redis"
    RABBIT = "rabbit"
    DYNAMIC_SCHEDULER = "dynamic-scheduler"


_CREATED: Final[str] = "create"
_REVERTED: Final[str] = "revert"

_CTX_VALUE: Final[str] = "a_value"


class _BS(BaseStep):
    @classmethod
    async def get_create_retries(cls, context: DeferredContext) -> int:
        _ = context
        return 10

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
        multiprocessing_queue: _AsyncMultiprocessingQueue = (
            app.state.multiprocessing_queue
        )
        await multiprocessing_queue.put((cls.__name__, _CREATED))

        return {
            **required_context,
            **{k: _CTX_VALUE for k in cls.get_create_provides_context_keys()},
        }

    @classmethod
    async def revert(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        multiprocessing_queue: _AsyncMultiprocessingQueue = (
            app.state.multiprocessing_queue
        )
        await multiprocessing_queue.put((cls.__name__, _REVERTED))

        return {
            **required_context,
            **{k: _CTX_VALUE for k in cls.get_revert_provides_context_keys()},
        }


class _BS1(_BS): ...


class _BS2(_BS): ...


class _BS3(_BS): ...


@pytest.mark.parametrize(
    "operation, expected_order",
    [
        pytest.param(
            [
                SingleStepGroup(_BS1),
            ],
            [
                CreateSequence(_BS1),
            ],
            id="s1",
        ),
        pytest.param(
            [
                ParallelStepGroup(_BS1, _BS2, _BS3),
            ],
            [
                CreateRandom(_BS1, _BS2, _BS3),
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
) -> None:
    operation_name: OperationName = "test_op"
    register_operation(operation_name, operation)
    process_manager.start(operation_name)

    service_manager = ServiceManager(redis_client_sdk, rabbit_client, paused_container)

    match interruption_type:
        case _InterruptionType.REDIS:
            print(f"[{interruption_type}]: will pause ⚙️")
            async with service_manager.pause_rabbit():
                print(f"[{interruption_type}]: paused ⏸️")

                await asyncio.sleep(_get_random_duration_before_interrupting())
            print(f"[{interruption_type}]: unpaused ⏯️")
        case _InterruptionType.RABBIT:
            print(f"[{interruption_type}]: will pause ⚙️")
            async with service_manager.pause_rabbit():
                print(f"[{interruption_type}]: paused ⏸️")

                await asyncio.sleep(_get_random_duration_before_interrupting())
            print(f"[{interruption_type}]: unpaused ⏯️")
        case _InterruptionType.DYNAMIC_SCHEDULER:
            print(f"[{interruption_type}]: will pause ⚙️")
            process_manager.kill()
            print(f"[{interruption_type}]: paused ⏸️")

            await asyncio.sleep(_get_random_duration_before_interrupting())
            process_manager.start(operation_name)
            print(f"[{interruption_type}]: unpaused ⏯️")
        case _:
            msg = f"Unhandled interruption_type={interruption_type}"
            raise RuntimeError(msg)

    await ensure_expected_order(queue_poller.events, expected_order)
