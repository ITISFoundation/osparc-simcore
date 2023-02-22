# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import asyncio
from typing import Any, Awaitable, Final

import pytest
from pydantic import NonNegativeInt
from servicelib.rabbitmq_robust_rpc import (
    NotStartedError,
    RemoteMethodNotRegisteredError,
    RobustRPCClient,
    RobustRPCServer,
)
from settings_library.rabbit import RabbitSettings

pytest_simcore_core_services_selection = [
    "rabbit",
]

MULTIPLE_REQUESTS_COUNT: Final[NonNegativeInt] = 100


@pytest.fixture
async def rpc_client(rabbit_service: RabbitSettings) -> RobustRPCClient:
    client = RobustRPCClient(rabbit_settings=rabbit_service)
    await client.start()
    yield client
    await client.stop()


@pytest.fixture
async def rpc_server(rabbit_service: RabbitSettings) -> RobustRPCServer:
    server = RobustRPCServer(rabbit_settings=rabbit_service)
    await server.start()
    yield server
    await server.stop()


async def add_me(*, x: Any, y: Any) -> Any:
    result = x + y
    # NOTE: types are not enforced
    # result's type will on the caller side will be the one it has here
    return result


class CustomClass:
    def __init__(self, x: Any, y: Any) -> None:
        self.x = x
        self.y = y

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} x={self.x}, y={self.y}>"

    def __eq__(self, other: "CustomClass") -> bool:
        return self.x == other.x and self.y == other.y

    def __add__(self, other: "CustomClass") -> "CustomClass":
        return CustomClass(x=self.x + other.x, y=self.y + other.y)


@pytest.mark.parametrize(
    "x,y,expected_result,expected_type",
    [
        pytest.param(12, 20, 32, int, id="expect_int"),
        pytest.param(12, 20.0, 32.0, float, id="expect_float"),
        pytest.param(b"123b", b"xyz0", b"123bxyz0", bytes, id="expect_bytes"),
        pytest.param([1, 2], [2, 3], [1, 2, 2, 3], list, id="list_addition"),
        pytest.param(
            CustomClass(2, 1),
            CustomClass(1, 2),
            CustomClass(3, 3),
            CustomClass,
            id="custom_class",
        ),
        pytest.param(
            CustomClass([{"p", "1"}], [{"h": 1}]),
            CustomClass([{3, b"bytes"}], [{"b": 2}]),
            CustomClass([{"p", "1"}, {3, b"bytes"}], [{"h": 1}, {"b": 2}]),
            CustomClass,
            id="custom_class_complex_objects",
        ),
    ],
)
async def test_base_rpc_pattern(
    rpc_client: RobustRPCClient,
    rpc_server: RobustRPCServer,
    x: Any,
    y: Any,
    expected_result: Any,
    expected_type: type,
):
    await rpc_server.register(add_me)

    request_result = await rpc_client.request(add_me.__name__, x=x, y=y)
    assert request_result == expected_result
    assert type(request_result) == expected_type


async def test_multiple_requests_sequence_same_server_and_client(
    rpc_client: RobustRPCClient, rpc_server: RobustRPCServer
):
    await rpc_server.register(add_me)

    for i in range(MULTIPLE_REQUESTS_COUNT):
        assert await rpc_client.request(add_me.__name__, x=1 + i, y=2 + i) == 3 + i * 2


async def test_multiple_requests_parallel_same_server_and_client(
    rpc_client: RobustRPCClient, rpc_server: RobustRPCServer
):
    await rpc_server.register(add_me)

    expected_result: list[int] = []
    requests: list[Awaitable] = []
    for i in range(MULTIPLE_REQUESTS_COUNT):
        requests.append(rpc_client.request(add_me.__name__, x=1 + i, y=2 + i))
        expected_result.append(3 + i * 2)

    assert await asyncio.gather(*requests) == expected_result


async def test_multiple_requests_parallel_same_server_different_clients(
    rabbit_service: RabbitSettings, rpc_server: RobustRPCServer
):
    await rpc_server.register(add_me)

    clients: list[RobustRPCClient] = []
    for _ in range(MULTIPLE_REQUESTS_COUNT):
        client = RobustRPCClient(rabbit_service)
        clients.append(client)

    # worst case scenario
    await asyncio.gather(*[c.start() for c in clients])

    requests: list[Awaitable] = []
    expected_result: list[int] = []
    for i in range(MULTIPLE_REQUESTS_COUNT):
        client = clients[i]
        requests.append(client.request(add_me.__name__, x=1 + i, y=2 + i))
        expected_result.append(3 + i * 2)

    assert await asyncio.gather(*requests) == expected_result

    # worst case scenario
    await asyncio.gather(*[c.stop() for c in clients])


async def test_raise_error_if_not_started(rabbit_service: RabbitSettings):
    client = RobustRPCClient(rabbit_settings=rabbit_service)
    with pytest.raises(NotStartedError):
        await client.request(add_me, x=1, y=2)

    # expect not to raise error
    await client.stop()

    server = RobustRPCServer(rabbit_settings=rabbit_service)
    with pytest.raises(NotStartedError):
        await server.register(add_me)

    # expect not to raise error
    await server.stop()


async def _assert_event_not_registered(rpc_client: RobustRPCClient):
    with pytest.raises(RemoteMethodNotRegisteredError) as exec_info:
        assert await rpc_client.request(add_me.__name__, x=1, y=3) == 3
    assert (
        f"Could not find a remote method named: '{add_me.__name__}'"
        in f"{exec_info.value}"
    )


async def test_server_not_started(rpc_client: RobustRPCClient):
    await _assert_event_not_registered(rpc_client)


async def test_server_handler_not_registered(
    rpc_client: RobustRPCClient, rpc_server: RobustRPCServer
):
    await _assert_event_not_registered(rpc_client)


async def test_request_is_missing_arguments(
    rpc_client: RobustRPCClient, rpc_server: RobustRPCServer
):
    await rpc_server.register(add_me)

    # missing 1 argument
    with pytest.raises(TypeError) as exec_info:
        await rpc_client.request(add_me.__name__, x=1)
    assert (
        f"{add_me.__name__}() missing 1 required keyword-only argument: 'y'"
        in f"{exec_info.value}"
    )

    # missing all arguments
    with pytest.raises(TypeError) as exec_info:
        await rpc_client.request(add_me.__name__)
    assert (
        f"{add_me.__name__}() missing 2 required keyword-only arguments: 'x' and 'y'"
        in f"{exec_info.value}"
    )


async def test_client_cancels_long_running_request_or_client_takes_too_much_to_respond(
    rpc_client: RobustRPCClient, rpc_server: RobustRPCServer
):
    async def _long_running(*, time_to_sleep: float) -> None:
        await asyncio.sleep(time_to_sleep)

    await rpc_server.register(_long_running)

    # this task will be cancelled
    with pytest.raises(asyncio.TimeoutError):
        await rpc_client.request(_long_running.__name__, time_to_sleep=10, timeout=0.5)


async def test_server_handler_raises_error(
    rpc_client: RobustRPCClient, rpc_server: RobustRPCServer
):
    async def _raising_error() -> None:
        raise RuntimeError("failed as requested")

    await rpc_server.register(_raising_error)

    with pytest.raises(RuntimeError) as exec_info:
        await rpc_client.request(_raising_error.__name__)
    assert "failed as requested" == f"{exec_info.value}"
