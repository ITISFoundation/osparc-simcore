# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import asyncio
import json
import random
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any, AsyncIterable, Final
from unittest.mock import Mock

import psutil
import pytest
from pydantic import NonNegativeFloat, NonNegativeInt
from servicelib.background_task import cancel_task
from servicelib.deferred_tasks import (
    BaseDeferredHandler,
    DeferredManager,
    FullStartContext,
    TaskUID,
    UserStartContext,
)
from servicelib.redis import RedisClientSDKHealthChecked
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisDatabase, RedisSettings
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = [
    "rabbit",
    "redis",
]
pytest_simcore_ops_services_selection = [
    "redis-commander",
]


_CONSTANT_RESULT: Final[str] = "always_the_same"


class ExampleDeferredHandler(BaseDeferredHandler[str]):
    @classmethod
    async def get_timeout(cls, start_context: FullStartContext) -> timedelta:
        return timedelta(seconds=60)

    @classmethod
    async def start_deferred(cls, sleep_duration: float) -> UserStartContext:
        return {"sleep_duration": sleep_duration}

    @classmethod
    async def on_deferred_created(
        cls, task_uid: TaskUID, start_context: FullStartContext
    ) -> None:
        scheduled_queue: asyncio.Queue = start_context["scheduled_queue"]
        await scheduled_queue.put(task_uid)

    @classmethod
    async def run_deferred(cls, start_context: FullStartContext) -> str:
        sleep_duration: float = start_context["sleep_duration"]
        await asyncio.sleep(sleep_duration)
        return _CONSTANT_RESULT

    @classmethod
    async def on_deferred_result(
        cls, result: str, start_context: FullStartContext
    ) -> None:
        result_queue: asyncio.Queue = start_context["result_queue"]
        await result_queue.put(result)


class ExampleApp:
    def __init__(
        self,
        rabbit_settings: RabbitSettings,
        redis_settings: RedisSettings,
        result_queue: asyncio.Queue,
        scheduled_queue: asyncio.Queue,
        max_workers: NonNegativeInt,
    ) -> None:
        self._redis_client = RedisClientSDKHealthChecked(
            redis_settings.build_redis_dsn(RedisDatabase.DEFERRED_TASKS)
        )
        self._manager = DeferredManager(
            rabbit_settings,
            self._redis_client,
            globals_for_start_context={
                "result_queue": result_queue,
                "scheduled_queue": scheduled_queue,
            },
            max_workers=max_workers,
        )

    async def setup(self) -> None:
        await self._redis_client.setup()
        await self._manager.setup()

    async def shutdown(self) -> None:
        await self._manager.shutdown()
        await self._redis_client.shutdown()


class _AppLifecycleManager:
    def __init__(
        self,
        rabbit_settings: RabbitSettings,
        redis_settings: RedisSettings,
        max_workers: NonNegativeInt,
        results_mock: Mock,
        scheduled_mock: Mock,
    ) -> None:
        self._result_queue: asyncio.Queue = asyncio.Queue()
        self._scheduled_queue: asyncio.Queue = asyncio.Queue()
        self._commands_queue: asyncio.Queue = asyncio.Queue()
        self.results_mock = results_mock
        self.scheduled_mock = scheduled_mock

        self._app = ExampleApp(
            rabbit_settings,
            redis_settings,
            self._result_queue,
            self._scheduled_queue,
            max_workers,
        )

        self._commands_task: asyncio.Task | None = None
        self._results_task: asyncio.Task | None = None
        self._scheduled_task: asyncio.Task | None = None

    async def _commands_worker(self) -> None:
        while True:
            command = await self._commands_queue.get()

            if command is None:
                break

            await ExampleDeferredHandler.start_deferred(**command)

    async def _results_worker(self) -> None:
        while True:
            result = await self._result_queue.get()
            self.results_mock(result)
            print("App Lifecycle -> JOB DONE")

    async def _scheduled_worker(self) -> None:
        while True:
            task_uid = await self._scheduled_queue.get()
            self.scheduled_mock(task_uid)
            print("App Lifecycle -> JOB SCHEDULED")

    async def start(self) -> None:
        assert self._commands_task is None
        assert self._results_task is None
        assert self._scheduled_task is None

        await self._app.setup()

        self._commands_task = asyncio.create_task(self._commands_worker())
        self._results_task = asyncio.create_task(self._results_worker())
        self._scheduled_task = asyncio.create_task(self._scheduled_worker())

        print("App Lifecycle -> STARTED")

    async def stop(self) -> None:
        assert self._commands_task is not None
        assert self._results_task is not None
        assert self._scheduled_task is not None

        await self._app.shutdown()

        # graceful shut down of deferred_manager
        await self._commands_queue.put(None)
        await asyncio.sleep(0.1)  # wait for manager shutdown

        await cancel_task(self._commands_task, timeout=1)
        self._commands_task = None

        await cancel_task(self._results_task, timeout=1)
        self._results_task = None

        await cancel_task(self._scheduled_task, timeout=1)
        self._scheduled_task = None

        print("App Lifecycle -> STOPPED")

    async def start_deferred_task(self, sleep_duration: float) -> None:
        await self._commands_queue.put({"sleep_duration": sleep_duration})

    async def __aenter__(self) -> "_AppLifecycleManager":
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.stop()
        # wait for all events to be consumed
        await asyncio.sleep(0.1)


async def _assert_mock_has_calls(
    mock: Mock, *, count: NonNegativeInt, timeout: float = 10
) -> None:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.01),
        stop=stop_after_delay(timeout),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            assert len(mock.call_args_list) == count


@pytest.mark.parametrize("max_workers", [10])
@pytest.mark.parametrize(
    "deferred_tasks_to_start",
    [
        # 1,
        2,
        # 100,
    ],
)
@pytest.mark.parametrize(
    "start_stop_cycles",
    [
        # 0
        1,
    ],
)
async def test_run_lots_of_jobs_interrupted(
    rabbit_service: RabbitSettings,
    redis_service: RedisSettings,
    max_workers: NonNegativeInt,
    deferred_tasks_to_start: NonNegativeInt,
    start_stop_cycles: NonNegativeInt,
):
    scheduled_mock = Mock()
    results_mock = Mock()

    async with _AppLifecycleManager(
        rabbit_service, redis_service, max_workers, results_mock, scheduled_mock
    ) as manager:

        # start all in parallel
        await asyncio.gather(
            *[manager.start_deferred_task(0.1) for _ in range(deferred_tasks_to_start)]
        )
        # makes sure tasks have been scheduled
        await _assert_mock_has_calls(scheduled_mock, count=deferred_tasks_to_start)

        # if this fails all scheduled tasks have already finished
        assert len(results_mock.call_args_list) < deferred_tasks_to_start

        # emulate issues with processing start & stop DeferredManager
        for _ in range(start_stop_cycles):
            await manager.stop()
            radom_wait = random.uniform(0.1, 0.2)  # noqa: S311
            await asyncio.sleep(radom_wait)
            await manager.start()

        await _assert_mock_has_calls(results_mock, count=deferred_tasks_to_start)


class _RemoteProcess:
    def __init__(self, shell_command):
        self.shell_command = shell_command
        self.process = None
        self.pid: int | None = None

    async def start(self):
        assert self.process is None
        assert self.pid is None

        self.process = await asyncio.create_subprocess_shell(self.shell_command)
        self.pid = self.process.pid
        print(f"Process started {self.pid}")

    async def stop(self):
        assert self.process is not None
        assert self.pid is not None

        parent = psutil.Process(self.pid)
        children = parent.children(recursive=True)
        for child_pid in [child.pid for child in children]:
            print(f"Killing {child_pid}")
            psutil.Process(child_pid).kill()

        parent.kill()
        print(f"Killing {parent.pid}")

        self.process = None
        self.pid = None


@pytest.fixture
async def remote_process() -> AsyncIterable[None]:
    python_interpreter = sys.executable
    current_module_path = (
        Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
    )
    app_to_start = current_module_path / "example_app.py"
    assert app_to_start.exists()

    process = _RemoteProcess(f"{python_interpreter} {app_to_start}")
    await process.start()

    yield None

    await process.stop()


async def _tcp_command(
    command: dict[str, Any],
    *,
    host: str = "127.0.0.1",
    port: int = 3562,
    buff_size: int = 10000,
    timeout: NonNegativeFloat = 1,
) -> Any:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(timeout),
        reraise=True,
    ):
        with attempt:
            reader, writer = await asyncio.open_connection(host, port)

    writer.write(json.dumps(command).encode())
    await writer.drain()
    response = await reader.read(buff_size)
    decoded_response = response.decode()
    writer.close()
    return json.loads(decoded_response)


async def test_with_remote_process(remote_process: None):

    request = {"hello": "bc-d"}
    response = await _tcp_command(request)
    assert response == request


# THIS could be the issue: ERROR    servicelib.deferred_tasks._utils:_utils.py:29 Error detected in user code. Aborting message retry. Please check code at: 'servicelib.deferred_tasks._deferred_manager._fs_handle_worker'
# It's in ERROR_RESULT when the thing was cancelled, should be in worker retry,
# I guess something went wrong? But why is the status in the DB wrong?
# Figure out from here
