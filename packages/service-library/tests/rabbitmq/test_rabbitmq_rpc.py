# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, Final

import pytest
from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import NonNegativeInt, ValidationError
from servicelib.rabbitmq import (
    RabbitMQRPCClient,
    RemoteMethodNotRegisteredError,
    RPCNamespace,
    RPCNotInitializedError,
)
from settings_library.rabbit import RabbitSettings

pytest_simcore_core_services_selection = [
    "rabbit",
]

MULTIPLE_REQUESTS_COUNT: Final[NonNegativeInt] = 100


@pytest.fixture
def namespace() -> RPCNamespace:
    return RPCNamespace.from_entries({f"test{i}": f"test{i}" for i in range(8)})


async def add_me(*, x: Any, y: Any) -> Any:
    return x + y
    # NOTE: types are not enforced
    # result's type will on the caller side will be the one it has here


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


@pytest.fixture
async def rpc_client(
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
) -> RabbitMQRPCClient:
    return await rabbitmq_rpc_client("pytest_rpc_client")


@pytest.fixture
async def rpc_server(
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
) -> RabbitMQRPCClient:
    return await rabbitmq_rpc_client("pytest_rpc_server")


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
    rpc_client: RabbitMQRPCClient,
    rpc_server: RabbitMQRPCClient,
    x: Any,
    y: Any,
    expected_result: Any,
    expected_type: type,
    namespace: RPCNamespace,
):
    await rpc_server.register_handler(namespace, RPCMethodName(add_me.__name__), add_me)

    request_result = await rpc_client.request(
        namespace, RPCMethodName(add_me.__name__), x=x, y=y
    )
    assert request_result == expected_result
    assert type(request_result) == expected_type

    await rpc_server.unregister_handler(add_me)


async def test_multiple_requests_sequence_same_replier_and_requester(
    rpc_client: RabbitMQRPCClient,
    rpc_server: RabbitMQRPCClient,
    namespace: RPCNamespace,
):
    await rpc_server.register_handler(namespace, RPCMethodName(add_me.__name__), add_me)

    for i in range(MULTIPLE_REQUESTS_COUNT):
        assert (
            await rpc_client.request(
                namespace, RPCMethodName(add_me.__name__), x=1 + i, y=2 + i
            )
            == 3 + i * 2
        )


async def test_multiple_requests_parallel_same_replier_and_requester(
    rpc_client: RabbitMQRPCClient,
    rpc_server: RabbitMQRPCClient,
    namespace: RPCNamespace,
):
    await rpc_server.register_handler(namespace, RPCMethodName(add_me.__name__), add_me)

    expected_result: list[int] = []
    requests: list[Awaitable] = []
    for i in range(MULTIPLE_REQUESTS_COUNT):
        requests.append(
            rpc_client.request(
                namespace, RPCMethodName(add_me.__name__), x=1 + i, y=2 + i
            )
        )
        expected_result.append(3 + i * 2)

    assert await asyncio.gather(*requests) == expected_result


async def test_multiple_requests_parallel_same_replier_different_requesters(
    rabbit_service: RabbitSettings,
    rpc_server: RabbitMQRPCClient,
    namespace: RPCNamespace,
):
    await rpc_server.register_handler(namespace, RPCMethodName(add_me.__name__), add_me)

    clients: list[RabbitMQRPCClient] = []
    for _ in range(MULTIPLE_REQUESTS_COUNT):
        client = await RabbitMQRPCClient.create(client_name="", settings=rabbit_service)
        clients.append(client)

    # worst case scenario
    requests: list[Awaitable] = []
    expected_result: list[int] = []
    for i in range(MULTIPLE_REQUESTS_COUNT):
        client = clients[i]
        requests.append(
            client.request(namespace, RPCMethodName(add_me.__name__), x=1 + i, y=2 + i)
        )
        expected_result.append(3 + i * 2)

    assert await asyncio.gather(*requests) == expected_result

    # worst case scenario
    await asyncio.gather(*[c.close() for c in clients])


async def test_raise_error_if_not_started(
    rabbit_service: RabbitSettings, namespace: RPCNamespace
):
    requester = RabbitMQRPCClient("", settings=rabbit_service)
    with pytest.raises(RPCNotInitializedError):
        await requester.request(namespace, RPCMethodName(add_me.__name__), x=1, y=2)

    # expect not to raise error
    await requester.close()

    replier = RabbitMQRPCClient("", settings=rabbit_service)
    with pytest.raises(RPCNotInitializedError):
        await replier.register_handler(
            namespace, RPCMethodName(add_me.__name__), add_me
        )

    with pytest.raises(RPCNotInitializedError):
        await replier.unregister_handler(add_me)

    # expect not to raise error
    await replier.close()


async def _assert_event_not_registered(
    rpc_client: RabbitMQRPCClient, namespace: RPCNamespace
):
    with pytest.raises(RemoteMethodNotRegisteredError) as exec_info:
        assert (
            await rpc_client.request(
                namespace, RPCMethodName(add_me.__name__), x=1, y=3
            )
            == 3
        )
    assert (
        f"Could not find a remote method named: '{namespace}.{RPCMethodName(add_me.__name__)}'"
        in f"{exec_info.value}"
    )


async def test_replier_not_started(
    rpc_client: RabbitMQRPCClient, namespace: RPCNamespace
):
    await _assert_event_not_registered(rpc_client, namespace)


async def test_replier_handler_not_registered(
    rpc_client: RabbitMQRPCClient,
    rpc_server: RabbitMQRPCClient,
    namespace: RPCNamespace,
):
    await _assert_event_not_registered(rpc_client, namespace)


async def test_request_is_missing_arguments(
    rpc_client: RabbitMQRPCClient,
    rpc_server: RabbitMQRPCClient,
    namespace: RPCNamespace,
):
    await rpc_server.register_handler(namespace, RPCMethodName(add_me.__name__), add_me)

    # missing 1 argument
    with pytest.raises(TypeError) as exec_info:
        await rpc_client.request(namespace, RPCMethodName(add_me.__name__), x=1)
    assert (
        f"{RPCMethodName(add_me.__name__)}() missing 1 required keyword-only argument: 'y'"
        in f"{exec_info.value}"
    )

    # missing all arguments
    with pytest.raises(TypeError) as exec_info:
        await rpc_client.request(namespace, RPCMethodName(add_me.__name__))
    assert (
        f"{RPCMethodName(add_me.__name__)}() missing 2 required keyword-only arguments: 'x' and 'y'"
        in f"{exec_info.value}"
    )


async def test_requester_cancels_long_running_request_or_requester_takes_too_much_to_respond(
    rpc_client: RabbitMQRPCClient,
    rpc_server: RabbitMQRPCClient,
    namespace: RPCNamespace,
):
    async def _long_running(*, time_to_sleep: float) -> None:
        await asyncio.sleep(time_to_sleep)

    await rpc_server.register_handler(
        namespace, RPCMethodName(_long_running.__name__), _long_running
    )

    with pytest.raises(asyncio.TimeoutError):
        await rpc_client.request(
            namespace,
            RPCMethodName(_long_running.__name__),
            time_to_sleep=3,
            timeout_s=1,
        )


async def test_replier_handler_raises_error(
    rpc_client: RabbitMQRPCClient,
    rpc_server: RabbitMQRPCClient,
    namespace: RPCNamespace,
):
    async def _raising_error() -> None:
        msg = "failed as requested"
        raise RuntimeError(msg)

    await rpc_server.register_handler(
        namespace, RPCMethodName(_raising_error.__name__), _raising_error
    )

    with pytest.raises(RuntimeError) as exec_info:
        await rpc_client.request(namespace, RPCMethodName(_raising_error.__name__))
    assert f"{exec_info.value}" == "failed as requested"


async def test_replier_responds_with_not_locally_defined_object_instance(
    rpc_client: RabbitMQRPCClient,
    rpc_server: RabbitMQRPCClient,
    namespace: RPCNamespace,
):
    async def _replier_scope() -> None:
        class Custom:
            def __init__(self, x: Any) -> None:
                self.x = x

        async def _get_custom(x: Any) -> Custom:
            return Custom(x)

        await rpc_server.register_handler(
            namespace, RPCMethodName("a_name"), _get_custom
        )

    async def _requester_scope() -> None:
        # NOTE: what is happening here?
        # the replier will say that it cannot pickle a local object and send it over
        # the server's request will just time out. I would prefer a cleaner interface.
        # There is no change of intercepting this message.
        with pytest.raises(
            AttributeError, match=r"Can't pickle local object .+.<locals>.Custom"
        ):
            await rpc_client.request(
                namespace, RPCMethodName("a_name"), x=10, timeout_s=1
            )

    await _replier_scope()
    await _requester_scope()


async def test_register_handler_under_same_name_raises_error(
    rpc_server: RabbitMQRPCClient, namespace: RPCNamespace
):
    async def _a_handler() -> None:
        pass

    async def _another_handler() -> None:
        pass

    await rpc_server.register_handler(namespace, RPCMethodName("same_name"), _a_handler)
    with pytest.raises(RuntimeError) as exec_info:
        await rpc_server.register_handler(
            namespace, RPCMethodName("same_name"), _another_handler
        )
    assert "Method name already used for" in f"{exec_info.value}"


@pytest.mark.parametrize(
    "handler_name, expect_fail",
    [
        ("a" * 254, True),
        ("a" * 253, False),
    ],
)
async def test_get_namespaced_method_name_max_length(
    rpc_server: RabbitMQRPCClient, handler_name: str, expect_fail: bool
):
    async def _a_handler() -> None:
        pass

    if expect_fail:
        with pytest.raises(
            ValidationError, match="String should have at most 255 characters"
        ):
            await rpc_server.register_handler(
                RPCNamespace("a"), RPCMethodName(handler_name), _a_handler
            )
    else:
        await rpc_server.register_handler(
            RPCNamespace("a"), RPCMethodName(handler_name), _a_handler
        )
