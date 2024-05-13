# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import asyncio
import contextlib
import json
import random
import sys
from collections.abc import AsyncIterable, AsyncIterator, Callable
from pathlib import Path
from typing import Any, Protocol

import aiodocker
import psutil
import pytest
from pydantic import NonNegativeFloat, NonNegativeInt, SecretStr
from pydantic.json import pydantic_encoder
from servicelib.rabbitmq import RabbitMQClient
from servicelib.redis import RedisClientSDK
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

    async def stop(self, *, graceful: bool = False):
        if not graceful:
            assert self.process is not None
            assert self.pid is not None

        parent = psutil.Process(self.pid)
        children = parent.children(recursive=True)
        for child_pid in [child.pid for child in children]:
            psutil.Process(child_pid).kill()

        self.process = None
        self.pid = None


@pytest.fixture
async def redis_client(redis_service: RedisSettings) -> AsyncIterator[RedisClientSDK]:
    redis_client_sdk = RedisClientSDK(
        redis_service.build_redis_dsn(RedisDatabase.DEFERRED_TASKS)
    )
    await redis_client_sdk.redis.flushall()
    yield redis_client_sdk
    await redis_client_sdk.redis.flushall()


@pytest.fixture
async def remote_process(redis_client: RedisClientSDK) -> AsyncIterable[_RemoteProcess]:
    python_interpreter = sys.executable
    current_module_path = (
        Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
    )
    app_to_start = current_module_path / "example_app.py"
    assert app_to_start.exists()

    process = _RemoteProcess(shell_command=f"{python_interpreter} {app_to_start}")

    yield process

    await process.stop(graceful=True)


async def _tcp_command(
    command: str,
    payload: dict[str, Any],
    *,
    host: str = "127.0.0.1",
    port: int = 3562,
    read_chunk_size: int = 10000,
    timeout: NonNegativeFloat = 1,
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
    def _show_secrets_encoder(obj):
        if isinstance(obj, SecretStr):
            return obj.get_secret_value()

        return pydantic_encoder(obj)

    return {
        "encoder": _show_secrets_encoder,
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
                "rabbit": self.rabbit_service.json(**_get_serialization_options()),
                "redis": self.redis_service.json(**_get_serialization_options()),
                "max-workers": self.max_workers,
            },
        )
        assert response is None

    async def stop(self) -> None:
        await self.remote_process.stop()

    async def start_deferred_task(
        self, sleep_duration: float, sequence_id: int
    ) -> None:
        response = await _tcp_command(
            "start", {"sleep_duration": sleep_duration, "sequence_id": sequence_id}
        )
        assert response is None

    async def get_results(self) -> list[str]:
        response = await _tcp_command("get-results", {})
        assert isinstance(response, list)
        return response

    async def get_scheduled(self) -> list[str]:
        response = await _tcp_command("get-scheduled", {})
        assert isinstance(response, list)
        return response


async def _assert_has_entries(
    manager: _RemoteProcessLifecycleManager,
    list_name: str,
    *,
    count: NonNegativeInt,
    timeout: float = 10,
) -> None:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.01),
        stop=stop_after_delay(timeout),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            if list_name == "get-results":
                results = await manager.get_results()
                # enure sequence numbers appear at least once
                # since results handler can be retries since they are interrupted
                assert len(results) >= count
                assert set(results) == {f"{x}" for x in range(count)}
            if list_name == "get-scheduled":
                scheduled = await manager.get_scheduled()
                assert len(scheduled) == count
                # ensure all entries are unique
                assert len(scheduled) == len(set(scheduled))


async def _sleep_in_interval(lower: NonNegativeFloat, upper: NonNegativeFloat) -> None:
    assert upper >= lower
    radom_wait = random.uniform(lower, upper)  # noqa: S311
    await asyncio.sleep(radom_wait)


@pytest.mark.parametrize("max_workers", [10])
@pytest.mark.parametrize(
    "deferred_tasks_to_start",
    [
        1,
        100,
    ],
)
@pytest.mark.parametrize(
    "start_stop_cycles",
    [
        0,
        10,
    ],
)
async def test_workflow_with_remote_process_interruptions(
    remote_process: _RemoteProcess,
    rabbit_service: RabbitSettings,
    redis_service: RedisSettings,
    max_workers: int,
    deferred_tasks_to_start: NonNegativeInt,
    start_stop_cycles: NonNegativeInt,
):
    async with _RemoteProcessLifecycleManager(
        remote_process, rabbit_service, redis_service, max_workers
    ) as manager:

        # start all in parallel
        await asyncio.gather(
            *[
                manager.start_deferred_task(0.1, i)
                for i in range(deferred_tasks_to_start)
            ]
        )
        # makes sure tasks have been scheduled
        await _assert_has_entries(
            manager, "get-scheduled", count=deferred_tasks_to_start
        )

        # if this fails all scheduled tasks have already finished
        assert len(await manager.get_results()) < deferred_tasks_to_start

        # emulate issues with processing start & stop DeferredManager
        for _ in range(start_stop_cycles):
            await manager.stop()
            await _sleep_in_interval(0.2, 0.4)
            await manager.start()

        await _assert_has_entries(manager, "get-results", count=deferred_tasks_to_start)


@pytest.fixture
async def async_docker_client() -> AsyncIterator[aiodocker.Docker]:
    async with aiodocker.Docker() as docker_client:
        yield docker_client


@contextlib.asynccontextmanager
async def paused_container(
    async_docker_client: aiodocker.Docker, container_name: str
) -> AsyncIterator[None]:
    containers = await async_docker_client.containers.list(
        filters={"name": [f"{container_name}."]}
    )
    await asyncio.gather(*(c.pause() for c in containers))
    # refresh
    container_attrs = await asyncio.gather(*(c.show() for c in containers))
    for container_status in container_attrs:
        assert container_status["State"]["Status"] == "paused"

    yield

    await asyncio.gather(*(c.unpause() for c in containers))
    # refresh
    container_attrs = await asyncio.gather(*(c.show() for c in containers))
    for container_status in container_attrs:
        assert container_status["State"]["Status"] == "running"
    # NOTE: container takes some time to start


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
        async_docker_client: aiodocker.Docker,
        redis_client: RedisClientSDK,
        rabbit_client: RabbitMQClient,
    ) -> None:
        self.async_docker_client = async_docker_client
        self.redis_client = redis_client
        self.rabbit_client = rabbit_client

    @contextlib.asynccontextmanager
    async def _pause_container(
        self, container_name: str, client: ClientWithPingProtocol
    ) -> AsyncIterator[None]:

        async with paused_container(self.async_docker_client, container_name):
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


@pytest.mark.parametrize("max_workers", [10])
@pytest.mark.parametrize("deferred_tasks_to_start", [100])
@pytest.mark.parametrize(
    "service",
    [
        "rabbit",
        "redis",
    ],
)
async def test_paused_services(
    async_docker_client: aiodocker.Docker,
    redis_client: RedisClientSDK,
    rabbit_client: RabbitMQClient,
    remote_process: _RemoteProcess,
    rabbit_service: RabbitSettings,
    redis_service: RedisSettings,
    max_workers: int,
    deferred_tasks_to_start: int,
    service: str,
):
    service_manager = ServiceManager(async_docker_client, redis_client, rabbit_client)

    async with _RemoteProcessLifecycleManager(
        remote_process, rabbit_service, redis_service, max_workers
    ) as manager:

        # start all in parallel
        await asyncio.gather(
            *[
                manager.start_deferred_task(0.1, i)
                for i in range(deferred_tasks_to_start)
            ]
        )
        # makes sure tasks have been scheduled
        await _assert_has_entries(
            manager, "get-scheduled", count=deferred_tasks_to_start
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

        await _assert_has_entries(manager, "get-results", count=deferred_tasks_to_start)
