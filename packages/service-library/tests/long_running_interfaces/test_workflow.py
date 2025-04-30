# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import asyncio
from collections.abc import AsyncIterable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import pytest
from pydantic import NonNegativeInt
from servicelib.long_running_interfaces import Client, LongRunningNamespace, Server
from servicelib.long_running_interfaces._errors import (
    NoMoreRetryAttemptsError,
    TimedOutError,
)
from servicelib.long_running_interfaces_runners.asyncio_tasks import (
    AsyncioTasksJobInterface,
    AsyncTaskRegistry,
)
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings

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
    async def sleep_forever_f() -> None:
        while True:  # noqa: ASYNC110
            await asyncio.sleep(1)

    server = Server(
        rabbit_service, long_running_namespace, AsyncioTasksJobInterface(registry)
    )

    await server.setup()
    yield server
    await server.teardown()


# Figure out how to cause interruption in SERVER & CLIENT code, in order to simulate shakyness in the tests
# write something that cancels and restarts the job runtime

# TODO: add the following tests
# start a job and wait for it to finish
# start a job that takes too much time
# start a job that raises an error
# start a job that after 95% of timeout raises an errors x times in a row (we can test if it can successfully finish)


@dataclass
class _CustomClass:
    number: float


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
    server: Server, client: Client, expected_type: type, echo_value: Any
):
    result = await client.ensure_result(
        "echo_f",
        expected_type=expected_type,
        timeout=timedelta(seconds=1),
        data=echo_value,
    )
    assert result == echo_value
    assert type(result) is expected_type


# TODO: count error in logs to be sure soemthing is worng
# TODO: count that it's missing with retry_count=0 and that it raises a vlidation error
# TODO: figure out a way to raise the error


async def test_timeout_error(server: Server, client: Client):
    with pytest.raises(TimedOutError):
        await client.ensure_result(
            "sleep_forever_f", expected_type=type(None), timeout=timedelta(seconds=1)
        )


async def test_timeout_during_failing_retry(server: Server, client: Client):
    with pytest.raises(TimedOutError):
        await client.ensure_result(
            "raising_after_sleep_f",
            expected_type=type(None),
            timeout=timedelta(seconds=2),
            retry_count=100,
            duration=1,
        )


@pytest.mark.parametrize("retry_count", [1, 2])
async def test_stops_after_n_retry_attempts(
    server: Server, client: Client, retry_count: NonNegativeInt
):
    with pytest.raises(NoMoreRetryAttemptsError):
        await client.ensure_result(
            "raising_f",
            expected_type=type(None),
            timeout=timedelta(seconds=10),
            retry_count=retry_count,
        )
