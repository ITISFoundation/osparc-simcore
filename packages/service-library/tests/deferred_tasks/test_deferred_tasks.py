# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import asyncio
import contextlib
import datetime
import itertools
import json
import random
import sys
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, AsyncExitStack, suppress
from pathlib import Path
from typing import Any, Protocol

import psutil
import pytest
from aiohttp.test_utils import unused_port
from common_library.json_serialization import json_dumps
from common_library.serialization import model_dump_with_secrets
from pydantic import NonNegativeFloat, NonNegativeInt
from pytest_mock import MockerFixture
from servicelib import redis as servicelib_redis
from servicelib.rabbitmq import RabbitMQClient
from servicelib.redis import RedisClientSDK
from servicelib.sequences_utils import partition_gen
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from tenacity.asyncio import AsyncRetrying
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


class _RemoteProcess:
    def __init__(self, shell_command, port: int):
        self.shell_command = shell_command
        self.port = port
        self.process = None
        self.pid: int | None = None

    async def start(self):
        assert self.process is None
        assert self.pid is None

        self.process = await asyncio.create_subprocess_shell(
            self.shell_command, env={"LISTEN_PORT": f"{self.port}"}
        )
        self.pid = self.process.pid

    async def stop(self, *, graceful: bool = False):
        if not graceful:
            assert self.process is not None
            assert self.pid is not None

        with suppress(psutil.NoSuchProcess):
            parent = psutil.Process(self.pid)
            children = parent.children(recursive=True)
            for child_pid in [child.pid for child in children]:
                with suppress(psutil.NoSuchProcess):
                    psutil.Process(child_pid).kill()

        self.process = None
        self.pid = None


@pytest.fixture
async def get_remote_process(
    redis_client_sdk_deferred_tasks: RedisClientSDK,
) -> AsyncIterable[Callable[[], Awaitable[_RemoteProcess]]]:
    python_interpreter = sys.executable
    current_module_path = (
        Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
    )
    app_to_start = current_module_path / "example_app.py"
    assert app_to_start.exists()

    started_processes: list[_RemoteProcess] = []

    async def _() -> _RemoteProcess:
        process = _RemoteProcess(
            shell_command=f"{python_interpreter} {app_to_start}", port=unused_port()
        )
        started_processes.append(process)
        return process

    yield _

    await asyncio.gather(
        *[process.stop(graceful=True) for process in started_processes]
    )


async def _tcp_command(
    command: str,
    payload: dict[str, Any],
    *,
    host: str = "localhost",
    port: int,
    read_chunk_size: int = 10000,
    timeout: NonNegativeFloat = 10,
) -> Any:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(timeout),
        reraise=True,
    ):
        with attempt:
            reader, writer = await asyncio.open_connection(host, port)

    writer.write(json.dumps({"command": command, "payload": payload}).encode())
    await writer.drain()
    response = await reader.read(read_chunk_size)
    decoded_response = response.decode()
    writer.close()
    return json.loads(decoded_response)


def _get_serialization_options() -> dict[str, Any]:
    return {
        "exclude_defaults": True,
        "exclude_none": True,
        "exclude_unset": True,
    }


class _RemoteProcessLifecycleManager:
    def __init__(
        self,
        remote_process: _RemoteProcess,
        rabbit_service: RabbitSettings,
        redis_service: RedisSettings,
        max_workers: int,
    ) -> None:
        self.remote_process = remote_process
        self.rabbit_service = rabbit_service
        self.redis_service = redis_service
        self.max_workers = max_workers

    async def __aenter__(self) -> "_RemoteProcessLifecycleManager":
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.stop()
        # wait for all events to be consumed
        await asyncio.sleep(0.1)

    async def start(self) -> None:
        await self.remote_process.start()

        response = await _tcp_command(
            "init-context",
            {
                "rabbit": json_dumps(
                    model_dump_with_secrets(
                        self.rabbit_service,
                        show_secrets=True,
                        **_get_serialization_options(),
                    )
                ),
                "redis": json_dumps(
                    model_dump_with_secrets(
                        self.redis_service,
                        show_secrets=True,
                        **_get_serialization_options(),
                    )
                ),
                "max-workers": self.max_workers,
            },
            port=self.remote_process.port,
        )
        assert response is None

    async def stop(self) -> None:
        await self.remote_process.stop()

    async def start_task(self, sleep_duration: float, sequence_id: int) -> None:
        response = await _tcp_command(
            "start",
            {"sleep_duration": sleep_duration, "sequence_id": sequence_id},
            port=self.remote_process.port,
        )
        assert response is None

    async def get_results(self) -> list[str]:
        response = await _tcp_command("get-results", {}, port=self.remote_process.port)
        assert isinstance(response, list)
        return response

    async def get_scheduled(self) -> list[str]:
        response = await _tcp_command(
            "get-scheduled", {}, port=self.remote_process.port
        )
        assert isinstance(response, list)
        return response


async def _assert_has_entries(
    managers: list[_RemoteProcessLifecycleManager],
    list_name: str,
    *,
    count: NonNegativeInt,
    timeout: float = 10,
    all_managers_have_some_entries: bool = False,
) -> None:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.01),
        stop=stop_after_delay(timeout),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            if list_name == "get-results":
                gathered_results: list[list[str]] = await asyncio.gather(
                    *[manager.get_results() for manager in managers]
                )
                if all_managers_have_some_entries:
                    for entry in gathered_results:
                        assert len(entry) > 0
                results: list[str] = list(itertools.chain(*gathered_results))
                # enure sequence numbers appear at least once
                # since results handler can be retries since they are interrupted
                assert len(results) >= count
                assert set(results) == {f"{x}" for x in range(count)}
            if list_name == "get-scheduled":
                gathered_results: list[list[str]] = await asyncio.gather(
                    *[manager.get_scheduled() for manager in managers]
                )
                if all_managers_have_some_entries:
                    for entry in gathered_results:
                        assert len(entry) > 0
                scheduled: list[str] = list(itertools.chain(*gathered_results))
                assert len(scheduled) == count
                # ensure all entries are unique
                assert len(scheduled) == len(set(scheduled))


async def _sleep_in_interval(lower: NonNegativeFloat, upper: NonNegativeFloat) -> None:
    assert upper >= lower
    radom_wait = random.uniform(lower, upper)  # noqa: S311
    await asyncio.sleep(radom_wait)


@pytest.mark.parametrize("remote_processes", [1, 10])
@pytest.mark.parametrize("max_workers", [10])
@pytest.mark.parametrize("deferred_tasks_to_start", [100])
@pytest.mark.parametrize("start_stop_cycles", [0, 10])
async def test_workflow_with_outages_in_process_running_deferred_manager(
    get_remote_process: Callable[[], Awaitable[_RemoteProcess]],
    rabbit_service: RabbitSettings,
    redis_service: RedisSettings,
    remote_processes: int,
    max_workers: int,
    deferred_tasks_to_start: NonNegativeInt,
    start_stop_cycles: NonNegativeInt,
):
    async with AsyncExitStack() as exit_stack:
        managers: list[_RemoteProcessLifecycleManager] = await asyncio.gather(
            *[
                exit_stack.enter_async_context(
                    _RemoteProcessLifecycleManager(
                        await get_remote_process(),
                        rabbit_service,
                        redis_service,
                        max_workers,
                    )
                )
                for i in range(remote_processes)
            ]
        )

        # pylint:disable=unnecessary-comprehension
        sequence_ids_list: list[tuple[int, ...]] = [  # noqa: C416
            x
            for x in partition_gen(
                range(deferred_tasks_to_start),
                slice_size=int(deferred_tasks_to_start / remote_processes) + 1,
            )
        ]
        assert sum(len(x) for x in sequence_ids_list) == deferred_tasks_to_start

        # start all in parallel divided among workers
        await asyncio.gather(
            *[
                manager.start_task(0.1, i)
                for manager, sequence_ids in zip(
                    managers, sequence_ids_list, strict=True
                )
                for i in sequence_ids
            ]
        )
        # makes sure tasks have been scheduled
        await _assert_has_entries(
            managers, "get-scheduled", count=deferred_tasks_to_start
        )

        # if this fails all scheduled tasks have already finished
        gathered_results: list[list[str]] = await asyncio.gather(
            *[manager.get_results() for manager in managers]
        )
        results: list[str] = list(itertools.chain(*gathered_results))
        assert len(results) <= deferred_tasks_to_start

        # emulate issues with processing start & stop DeferredManager
        for _ in range(start_stop_cycles):
            # pick a random manager to stop and resume
            manager = random.choice(managers)  # noqa: S311
            await manager.stop()
            await _sleep_in_interval(0.2, 0.4)
            await manager.start()

        await _assert_has_entries(
            managers,
            "get-results",
            count=deferred_tasks_to_start,
            all_managers_have_some_entries=True,
        )


@pytest.fixture
async def rabbit_client(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
) -> RabbitMQClient:
    return create_rabbitmq_client("pinger")


class ClientWithPingProtocol(Protocol):
    async def ping(self) -> bool:
        ...


class ServiceManager:
    def __init__(
        self,
        redis_client: RedisClientSDK,
        rabbit_client: RabbitMQClient,
        paused_container: Callable[[str], AbstractAsyncContextManager[None]],
    ) -> None:
        self.redis_client = redis_client
        self.rabbit_client = rabbit_client
        self.paused_container = paused_container

    @contextlib.asynccontextmanager
    async def _pause_container(
        self, container_name: str, client: ClientWithPingProtocol
    ) -> AsyncIterator[None]:

        async with self.paused_container(container_name):
            async for attempt in AsyncRetrying(
                wait=wait_fixed(0.1),
                stop=stop_after_delay(10),
                reraise=True,
                retry=retry_if_exception_type(AssertionError),
            ):
                with attempt:
                    assert await client.ping() is False
            yield

        async for attempt in AsyncRetrying(
            wait=wait_fixed(0.1),
            stop=stop_after_delay(10),
            reraise=True,
            retry=retry_if_exception_type(AssertionError),
        ):
            with attempt:
                assert await client.ping() is True

    @contextlib.asynccontextmanager
    async def pause_rabbit(self) -> AsyncIterator[None]:
        async with self._pause_container("rabbit", self.rabbit_client):
            yield

    @contextlib.asynccontextmanager
    async def pause_redis(self) -> AsyncIterator[None]:
        # save db for clean restore point
        await self.redis_client.redis.save()

        async with self._pause_container("redis", self.redis_client):
            yield


@pytest.fixture
def mock_default_socket_timeout(mocker: MockerFixture) -> None:
    mocker.patch.object(
        servicelib_redis, "_DEFAULT_SOCKET_TIMEOUT", datetime.timedelta(seconds=0.25)
    )


@pytest.mark.parametrize("max_workers", [10])
@pytest.mark.parametrize("deferred_tasks_to_start", [100])
@pytest.mark.parametrize("service", ["rabbit", "redis"])
async def test_workflow_with_third_party_services_outages(
    mock_default_socket_timeout: None,
    paused_container: Callable[[str], AbstractAsyncContextManager[None]],
    redis_client_sdk_deferred_tasks: RedisClientSDK,
    rabbit_client: RabbitMQClient,
    get_remote_process: Callable[[], Awaitable[_RemoteProcess]],
    rabbit_service: RabbitSettings,
    redis_service: RedisSettings,
    max_workers: int,
    deferred_tasks_to_start: int,
    service: str,
):
    service_manager = ServiceManager(
        redis_client_sdk_deferred_tasks, rabbit_client, paused_container
    )

    async with _RemoteProcessLifecycleManager(
        await get_remote_process(),
        rabbit_service,
        redis_service,
        max_workers,
    ) as manager:

        # start all in parallel
        await asyncio.gather(
            *[manager.start_task(0.1, i) for i in range(deferred_tasks_to_start)]
        )
        # makes sure tasks have been scheduled
        await _assert_has_entries(
            [manager], "get-scheduled", count=deferred_tasks_to_start
        )

        # if this fails all scheduled tasks have already finished
        assert len(await manager.get_results()) < deferred_tasks_to_start

        # emulate issues with 3rd party services
        match service:
            case "rabbit":
                print("[rabbit]: pausing")
                async with service_manager.pause_rabbit():
                    print("[rabbit]: paused")
                    await _sleep_in_interval(0.2, 0.4)
                print("[rabbit]: resumed")

            case "redis":
                print("[redis]: pausing")
                async with service_manager.pause_redis():
                    print("[redis]: paused")
                    await _sleep_in_interval(0.2, 0.4)
                print("[redis]: resumed")

        await _assert_has_entries(
            [manager], "get-results", count=deferred_tasks_to_start
        )
