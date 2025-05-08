# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import asyncio
from collections.abc import AsyncIterable, Awaitable, Callable, Iterator
from dataclasses import dataclass
from datetime import timedelta
from multiprocessing import Process
from typing import Any

import pytest
from pydantic import NonNegativeInt, ValidationError
from servicelib.async_utils import cancel_wait_task
from servicelib.resilent_long_running import (
    Client,
    FinishedWithError,
    LongRunningNamespace,
    Server,
    TimedOutError,
)
from servicelib.resilent_long_running._models import JobUniqueId
from servicelib.resilent_long_running.runners.asyncio_tasks import (
    AsyncioTasksJobInterface,
    AsyncTaskRegistry,
)
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)

pytest_simcore_core_services_selection = [
    "rabbit",
    "redis",
]


@pytest.fixture
async def client(
    redis_service: RedisSettings,
    rabbit_service: RabbitSettings,
    long_running_namespace: LongRunningNamespace,
) -> AsyncIterable[Client]:
    client = Client(rabbit_service, redis_service, long_running_namespace)

    await client.setup()
    yield client
    await client.teardown()


@pytest.fixture
async def server(
    rabbit_service: RabbitSettings, long_running_namespace: LongRunningNamespace
) -> AsyncIterable[Server]:

    registry = AsyncTaskRegistry()

    @registry.expose()
    async def some_f() -> None:
        pass

    @registry.expose()
    async def echo_f(data: Any) -> Any:
        return data

    @registry.expose()
    async def raising_f() -> None:
        msg = "I always raise an error"
        raise RuntimeError(msg)

    @registry.expose()
    async def raising_after_sleep_f(duration: float) -> None:
        await asyncio.sleep(duration)
        msg = "I always raise an error"
        raise RuntimeError(msg)

    @registry.expose()
    async def sleep_for_f(duration: float) -> None:
        await asyncio.sleep(duration)

    @registry.expose()
    async def sleep_forever_f() -> None:
        while True:  # noqa: ASYNC110
            await asyncio.sleep(1)

    server = Server(
        rabbit_service, long_running_namespace, AsyncioTasksJobInterface(registry)
    )

    await server.setup()
    yield server
    await server.teardown()


@dataclass
class _CustomClass:
    number: float


@pytest.mark.parametrize("is_unique", [True, False])
@pytest.mark.parametrize(
    "expected_type, echo_value",
    [
        (_CustomClass, _CustomClass(number=34)),
        (int, 23),
        (float, 23.45),
        (str, ""),
        (list, []),
        (list, [1, "b"]),
        (dict, {}),
        (dict, {"a": "dict"}),
        (set, {"a", "set"}),
        (type(None), None),
    ],
)
async def test_workflow(
    server: Server,
    client: Client,
    expected_type: type,
    echo_value: Any,
    is_unique: bool,
):
    result = await client.ensure_result(
        "echo_f",
        expected_type=expected_type,
        timeout=timedelta(seconds=1),
        data=echo_value,
        is_unique=is_unique,
    )
    assert result == echo_value
    assert type(result) is expected_type


@pytest.mark.parametrize("is_unique", [True, False])
async def test_timeout_error(server: Server, client: Client, is_unique: bool):
    with pytest.raises(TimedOutError):
        await client.ensure_result(
            "sleep_forever_f",
            expected_type=type(None),
            timeout=timedelta(seconds=1),
            is_unique=is_unique,
        )


@pytest.mark.parametrize("is_unique", [True, False])
async def test_timeout_during_failing_retry(
    server: Server, client: Client, is_unique: bool
):
    with pytest.raises(TimedOutError):
        await client.ensure_result(
            "raising_after_sleep_f",
            expected_type=type(None),
            timeout=timedelta(seconds=2),
            retry_count=100,
            duration=1,
            is_unique=is_unique,
        )


@pytest.mark.parametrize("retry_count", [1, 2])
@pytest.mark.parametrize("is_unique", [True, False])
async def test_raisese_after_n_retry_attempts(
    server: Server, client: Client, retry_count: NonNegativeInt, is_unique: bool
):
    with pytest.raises(FinishedWithError):
        await client.ensure_result(
            "raising_f",
            expected_type=type(None),
            timeout=timedelta(seconds=10),
            retry_count=retry_count,
            is_unique=is_unique,
        )


@pytest.mark.parametrize("is_unique", [True, False])
async def test_timeout_error_retry_count_zero(
    server: Server, client: Client, is_unique: bool
):
    with pytest.raises(ValidationError) as exec_info:
        await client.ensure_result(
            "some_f",
            expected_type=type(None),
            timeout=timedelta(seconds=10),
            retry_count=0,
            is_unique=is_unique,
        )

    assert "retry_count" in f"{exec_info.value}"
    assert "Input should be greater than 0" in f"{exec_info.value}"


def _get_tasks(server: Server) -> dict[JobUniqueId, asyncio.Task]:
    assert isinstance(server.rpc_interface.job_interface, AsyncioTasksJobInterface)
    # pylint:disable=protected-access
    return server.rpc_interface.job_interface._tasks  # noqa: SLF001


@retry(
    wait=wait_fixed(0.1),
    stop=stop_after_delay(5),
    retry=retry_if_exception_type(AssertionError),
)  # NOTE: function has to be async or the loop does not get a cahce to switch between retries
async def _assert_tasks_count(server: Server, count: int) -> None:
    tasks = _get_tasks(server)
    assert len(tasks.values()) == count


@pytest.mark.parametrize("is_unique", [True, False])
async def test_cancellation_from_client(
    server: Server, client: Client, is_unique: bool
):
    async def _to_run() -> None:
        await client.ensure_result(
            "sleep_forever_f",
            expected_type=type(None),
            timeout=timedelta(seconds=1),
            is_unique=is_unique,
        )

    await _assert_tasks_count(server, count=0)

    task = asyncio.create_task(_to_run())
    await _assert_tasks_count(server, count=1)

    # cancel from client side
    await cancel_wait_task(task, max_delay=5)
    await _assert_tasks_count(server, count=0)


async def _cancel_task_in_server(server: Server) -> None:
    tasks = _get_tasks(server)
    assert len(tasks.values()) == 1

    for task in tasks.values():
        task.cancel()


async def _sleep_for_ensure_result(
    client: Client,
    retry_count: NonNegativeInt,
    *,
    is_unique: bool,
    timeout: timedelta = timedelta(seconds=10),  # noqa: ASYNC109
) -> None:
    result = await client.ensure_result(
        "sleep_for_f",
        expected_type=type(None),
        timeout=timeout,
        duration=2,
        is_unique=is_unique,
        retry_count=retry_count,
    )
    assert result is None


@pytest.mark.parametrize("is_unique", [True, False])
async def test_cancellation_from_server_retires_and_finishes(
    server: Server, client: Client, is_unique: bool
):
    await _assert_tasks_count(server, count=0)

    task = asyncio.create_task(
        _sleep_for_ensure_result(client, retry_count=3, is_unique=is_unique)
    )
    await _assert_tasks_count(server, count=1)

    await _cancel_task_in_server(server)

    await task


@pytest.mark.parametrize("is_unique", [True, False])
async def test_cancellation_from_server_fails_if_no_more_retries_available(
    server: Server, client: Client, is_unique: bool
):
    await _assert_tasks_count(server, count=0)

    task = asyncio.create_task(
        _sleep_for_ensure_result(client, retry_count=1, is_unique=is_unique)
    )
    await _assert_tasks_count(server, count=1)

    await _cancel_task_in_server(server)

    with pytest.raises(FinishedWithError) as exec_info:
        await task
    assert exec_info.value.error == asyncio.CancelledError


@pytest.fixture
def client_process(
    redis_service: RedisSettings,
    rabbit_service: RabbitSettings,
    long_running_namespace: LongRunningNamespace,
) -> Iterator[Callable[[Callable[[Client], Awaitable[None]]], Process]]:
    started_processes: list[Process] = []

    def _(task_to_run: Callable[[Client], Awaitable[None]]) -> Process:

        def _process_worker() -> None:
            async def main():
                client = Client(rabbit_service, redis_service, long_running_namespace)
                await client.setup()
                await task_to_run(client)

            asyncio.run(main())

        process = Process(target=_process_worker, daemon=True)
        process.start()
        started_processes.append(process)
        return process

    yield _

    for process in started_processes:
        process.kill()


@pytest.mark.parametrize("is_unique", [False])
async def test_cancellation_of_client_can_resume_process(
    server: Server,
    client_process: Callable[[Callable[[Client], Awaitable[None]]], Process],
    client: Client,
    is_unique: bool,
):
    await _assert_tasks_count(server, count=0)

    async def _runner(client_: Client) -> None:
        await _sleep_for_ensure_result(
            client_, retry_count=3, timeout=timedelta(minutes=1), is_unique=is_unique
        )

    # start task in process
    process = client_process(_runner)
    await _assert_tasks_count(server, count=1)

    # kill process (client no longer talks with the server)
    process.kill()
    await _assert_tasks_count(server, count=1)

    # resume from a completly different process
    await _runner(client)
    # finishes original task
    await _assert_tasks_count(server, count=0)
