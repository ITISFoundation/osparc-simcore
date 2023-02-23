# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import asyncio
from typing import Any, Awaitable, Final

import pytest
from pydantic import NonNegativeInt
from servicelib.rabbitmq import PlatformNamespace, RabbitMQClient
from servicelib.rabbitmq_errors import (
    RemoteMethodNotRegisteredError,
    RPCNotInitializedError,
)
from settings_library.rabbit import RabbitSettings

pytest_simcore_core_services_selection = [
    "rabbit",
]

MULTIPLE_REQUESTS_COUNT: Final[NonNegativeInt] = 100


@pytest.fixture
def platform_namespace() -> PlatformNamespace:
    return "namespace"


@pytest.fixture
async def rabbit_requester(rabbit_service: RabbitSettings) -> RabbitMQClient:
    client = RabbitMQClient(client_name="requester", settings=rabbit_service)
    await client.rpc_initialize()
    yield client
    await client.close()


@pytest.fixture
async def rabbit_replier(rabbit_service: RabbitSettings) -> RabbitMQClient:
    client = RabbitMQClient(client_name="replier", settings=rabbit_service)
    await client.rpc_initialize()
    yield client
    await client.close()


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
    rabbit_requester: RabbitMQClient,
    rabbit_replier: RabbitMQClient,
    x: Any,
    y: Any,
    expected_result: Any,
    expected_type: type,
    platform_namespace: PlatformNamespace,
):
    await rabbit_replier.rpc_register(platform_namespace, add_me)

    request_result = await rabbit_requester.rpc_request(
        platform_namespace, add_me.__name__, x=x, y=y
    )
    assert request_result == expected_result
    assert type(request_result) == expected_type


async def test_multiple_requests_sequence_same_replier_and_requester(
    rabbit_requester: RabbitMQClient,
    rabbit_replier: RabbitMQClient,
    platform_namespace: PlatformNamespace,
):
    await rabbit_replier.rpc_register(platform_namespace, add_me)

    for i in range(MULTIPLE_REQUESTS_COUNT):
        assert (
            await rabbit_requester.rpc_request(
                platform_namespace, add_me.__name__, x=1 + i, y=2 + i
            )
            == 3 + i * 2
        )


async def test_multiple_requests_parallel_same_replier_and_requester(
    rabbit_requester: RabbitMQClient,
    rabbit_replier: RabbitMQClient,
    platform_namespace: PlatformNamespace,
):
    await rabbit_replier.rpc_register(platform_namespace, add_me)

    expected_result: list[int] = []
    requests: list[Awaitable] = []
    for i in range(MULTIPLE_REQUESTS_COUNT):
        requests.append(
            rabbit_requester.rpc_request(
                platform_namespace, add_me.__name__, x=1 + i, y=2 + i
            )
        )
        expected_result.append(3 + i * 2)

    assert await asyncio.gather(*requests) == expected_result


async def test_multiple_requests_parallel_same_replier_different_requesters(
    rabbit_service: RabbitSettings,
    rabbit_replier: RabbitMQClient,
    platform_namespace: PlatformNamespace,
):
    await rabbit_replier.rpc_register(platform_namespace, add_me)

    clients: list[RabbitMQClient] = []
    for _ in range(MULTIPLE_REQUESTS_COUNT):
        client = RabbitMQClient("", rabbit_service)
        clients.append(client)

    # worst case scenario
    await asyncio.gather(*[c.rpc_initialize() for c in clients])

    requests: list[Awaitable] = []
    expected_result: list[int] = []
    for i in range(MULTIPLE_REQUESTS_COUNT):
        client = clients[i]
        requests.append(
            client.rpc_request(platform_namespace, add_me.__name__, x=1 + i, y=2 + i)
        )
        expected_result.append(3 + i * 2)

    assert await asyncio.gather(*requests) == expected_result

    # worst case scenario
    await asyncio.gather(*[c.close() for c in clients])


async def test_raise_error_if_not_started(
    rabbit_service: RabbitSettings, platform_namespace: PlatformNamespace
):
    requester = RabbitMQClient("", settings=rabbit_service)
    with pytest.raises(RPCNotInitializedError):
        await requester.rpc_request(platform_namespace, add_me.__name__, x=1, y=2)

    # expect not to raise error
    await requester.close()

    replier = RabbitMQClient("", settings=rabbit_service)
    with pytest.raises(RPCNotInitializedError):
        await replier.rpc_register(platform_namespace, add_me)

    # expect not to raise error
    await replier.close()


async def _assert_event_not_registered(
    rabbit_requester: RabbitMQClient, platform_namespace: PlatformNamespace
):
    with pytest.raises(RemoteMethodNotRegisteredError) as exec_info:
        assert (
            await rabbit_requester.rpc_request(
                platform_namespace, add_me.__name__, x=1, y=3
            )
            == 3
        )
    assert (
        f"Could not find a remote method named: '{platform_namespace}.{add_me.__name__}'"
        in f"{exec_info.value}"
    )


async def test_replier_not_started(
    rabbit_requester: RabbitMQClient, platform_namespace: PlatformNamespace
):
    await _assert_event_not_registered(rabbit_requester, platform_namespace)


async def test_replier_handler_not_registered(
    rabbit_requester: RabbitMQClient,
    rabbit_replier: RabbitMQClient,
    platform_namespace: PlatformNamespace,
):
    await _assert_event_not_registered(rabbit_requester, platform_namespace)


async def test_request_is_missing_arguments(
    rabbit_requester: RabbitMQClient,
    rabbit_replier: RabbitMQClient,
    platform_namespace: PlatformNamespace,
):
    await rabbit_replier.rpc_register(platform_namespace, add_me)

    # missing 1 argument
    with pytest.raises(TypeError) as exec_info:
        await rabbit_requester.rpc_request(platform_namespace, add_me.__name__, x=1)
    assert (
        f"{add_me.__name__}() missing 1 required keyword-only argument: 'y'"
        in f"{exec_info.value}"
    )

    # missing all arguments
    with pytest.raises(TypeError) as exec_info:
        await rabbit_requester.rpc_request(platform_namespace, add_me.__name__)
    assert (
        f"{add_me.__name__}() missing 2 required keyword-only arguments: 'x' and 'y'"
        in f"{exec_info.value}"
    )


async def test_requester_cancels_long_running_request_or_requester_takes_too_much_to_respond(
    rabbit_requester: RabbitMQClient,
    rabbit_replier: RabbitMQClient,
    platform_namespace: PlatformNamespace,
):
    async def _long_running(*, time_to_sleep: float) -> None:
        await asyncio.sleep(time_to_sleep)

    await rabbit_replier.rpc_register(platform_namespace, _long_running)

    with pytest.raises(asyncio.TimeoutError):
        await rabbit_requester.rpc_request(
            platform_namespace, _long_running.__name__, time_to_sleep=3, timeout=1
        )


async def test_replier_handler_raises_error(
    rabbit_requester: RabbitMQClient,
    rabbit_replier: RabbitMQClient,
    platform_namespace: PlatformNamespace,
):
    async def _raising_error() -> None:
        raise RuntimeError("failed as requested")

    await rabbit_replier.rpc_register(platform_namespace, _raising_error)

    with pytest.raises(RuntimeError) as exec_info:
        await rabbit_requester.rpc_request(platform_namespace, _raising_error.__name__)
    assert "failed as requested" == f"{exec_info.value}"
