# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import asyncio
import json
import random
import sys
from collections.abc import AsyncIterable, AsyncIterator
from pathlib import Path
from typing import Any

import psutil
import pytest
from pydantic import NonNegativeFloat, NonNegativeInt, SecretStr
from pydantic.json import pydantic_encoder
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
        print(f"Process started {self.pid}")

    async def stop(self, *, graceful: bool = False):
        if not graceful:
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
async def cleanup_redis(redis_service: RedisSettings) -> AsyncIterator[None]:
    redis_client_sdk = RedisClientSDK(
        redis_service.build_redis_dsn(RedisDatabase.DEFERRED_TASKS)
    )
    await redis_client_sdk.redis.flushall()
    yield
    await redis_client_sdk.redis.flushall()


@pytest.fixture
async def remote_process(cleanup_redis: None) -> AsyncIterable[_RemoteProcess]:
    python_interpreter = sys.executable
    current_module_path = (
        Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
    )
    app_to_start = current_module_path / "example_app.py"
    assert app_to_start.exists()

    process = _RemoteProcess(f"{python_interpreter} {app_to_start}")

    yield process

    await process.stop(graceful=True)


async def _tcp_command(
    command: str,
    payload: dict[str, Any],
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

    writer.write(json.dumps({"command": command, "payload": payload}).encode())
    await writer.drain()
    response = await reader.read(buff_size)
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

    async def start_deferred_task(self, sleep_duration: float) -> None:
        response = await _tcp_command("start", {"sleep_duration": sleep_duration})
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
                assert len(await manager.get_results()) == count
            if list_name == "get-scheduled":
                assert len(await manager.get_scheduled()) == count


@pytest.mark.parametrize("max_workers", [10])
@pytest.mark.parametrize(
    "deferred_tasks_to_start",
    [
        # 1,
        # 2,
        40,
    ],
)
@pytest.mark.parametrize(
    "start_stop_cycles",
    [
        # 0,
        1,
    ],
)
async def test_with_remote_process(
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
            *[manager.start_deferred_task(0.1) for _ in range(deferred_tasks_to_start)]
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
            radom_wait = random.uniform(0.1, 0.2)  # noqa: S311
            await asyncio.sleep(radom_wait)
            await manager.start()

        await _assert_has_entries(manager, "get-results", count=deferred_tasks_to_start)
