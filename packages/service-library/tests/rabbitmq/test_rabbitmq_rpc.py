# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import asyncio
from collections.abc import Awaitable
from typing import Any, Final, TypeVar

import pytest
from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import NonNegativeInt, TypeAdapter, ValidationError
from servicelib.rabbitmq import (
    RabbitMQRPCClient,
    RemoteMethodNotRegisteredError,
    RPCNamespace,
    RPCNotInitializedError,
)
from servicelib.rabbitmq._client_rpc import _from_bytes, _to_bytes, rpc_server_lfespan
from settings_library.rabbit import RabbitSettings

pytest_simcore_core_services_selection = [
    "rabbit",
]

MULTIPLE_REQUESTS_COUNT: Final[NonNegativeInt] = 100


T = TypeVar("T", int, float, complex)


def add_me(x: bytes, y: bytes) -> bytes:
    result = x + y
    print("SSS: add_me", type(result), result)
    return result
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


@pytest.mark.parametrize(
    "obj",
    [
        1,
        1.1,
        b"123b",
        "sad",
        [1, 2],
        CustomClass(2, 1),
    ],
)
def test_custom_encoder_decoder(obj: Any):
    encoded_obj = _to_bytes(obj)
    assert isinstance(encoded_obj, bytes)
    result = _from_bytes(encoded_obj)
    assert type(result) is type(obj)
    assert result == obj


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
    await rpc_server.register_handler(
        namespace, TypeAdapter(RPCMethodName).validate_python(add_me.__name__), add_me
    )

    async with rpc_server_lfespan(rpc_server), rpc_server_lfespan(rpc_client):
        request_result = await rpc_client.request(
            namespace,
            TypeAdapter(RPCMethodName).validate_python(add_me.__name__),
            x=x,
            y=y,
        )
        assert request_result == expected_result
        assert type(request_result) is expected_type

    await rpc_server.unregister_handler(add_me)


async def test_multiple_requests_sequence_same_replier_and_requester(
    rpc_client: RabbitMQRPCClient,
    rpc_server: RabbitMQRPCClient,
    namespace: RPCNamespace,
):
    await rpc_server.register_handler(
        namespace, TypeAdapter(RPCMethodName).validate_python(add_me.__name__), add_me
    )

    async with rpc_server_lfespan(rpc_server), rpc_server_lfespan(rpc_client):
        for i in range(MULTIPLE_REQUESTS_COUNT):
            assert (
                await rpc_client.request(
                    namespace,
                    TypeAdapter(RPCMethodName).validate_python(add_me.__name__),
                    x=1 + i,
                    y=2 + i,
                )
                == 3 + i * 2
            )


async def test_register_handler_multiple_times(
    rpc_client: RabbitMQRPCClient,
    rpc_server: RabbitMQRPCClient,
    namespace: RPCNamespace,
):
    for _ in range(10):
        await rpc_server.register_handler(
            namespace,
            TypeAdapter(RPCMethodName).validate_python(add_me.__name__),
            add_me,
        )


async def test_multiple_requests_parallel_same_replier_and_requester(
    rpc_client: RabbitMQRPCClient,
    rpc_server: RabbitMQRPCClient,
    namespace: RPCNamespace,
):
    await rpc_server.register_handler(
        namespace, TypeAdapter(RPCMethodName).validate_python(add_me.__name__), add_me
    )

    expected_result: list[int] = []
    requests: list[Awaitable] = []

    async with rpc_server_lfespan(rpc_server), rpc_server_lfespan(rpc_client):
        for i in range(MULTIPLE_REQUESTS_COUNT):
            requests.append(
                rpc_client.request(
                    namespace,
                    TypeAdapter(RPCMethodName).validate_python(add_me.__name__),
                    x=1 + i,
                    y=2 + i,
                )
            )
            expected_result.append(3 + i * 2)

        assert await asyncio.gather(*requests) == expected_result


async def test_multiple_requests_parallel_same_replier_different_requesters(
    rabbit_service: RabbitSettings,
    rpc_server: RabbitMQRPCClient,
    namespace: RPCNamespace,
):
    await rpc_server.register_handler(
        namespace, TypeAdapter(RPCMethodName).validate_python(add_me.__name__), add_me
    )

    clients: list[RabbitMQRPCClient] = []
    async with rpc_server_lfespan(rpc_server):
        for _ in range(MULTIPLE_REQUESTS_COUNT):
            client = RabbitMQRPCClient.create(client_name="", settings=rabbit_service)
            clients.append(client)
            await client.start()

        # worst case scenario
        requests: list[Awaitable] = []
        expected_result: list[int] = []
        for i in range(MULTIPLE_REQUESTS_COUNT):
            client = clients[i]
            requests.append(
                client.request(
                    namespace,
                    TypeAdapter(RPCMethodName).validate_python(add_me.__name__),
                    x=1 + i,
                    y=2 + i,
                )
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
        await requester.request(
            namespace,
            TypeAdapter(RPCMethodName).validate_python(add_me.__name__),
            x=1,
            y=2,
        )

    # expect not to raise error
    await requester.close()

    replier = RabbitMQRPCClient("", settings=rabbit_service)
    with pytest.raises(RPCNotInitializedError):
        await replier.register_handler(
            namespace,
            TypeAdapter(RPCMethodName).validate_python(add_me.__name__),
            add_me,
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
                namespace,
                TypeAdapter(RPCMethodName).validate_python(add_me.__name__),
                x=1,
                y=3,
            )
            == 3
        )
    assert (
        f"Could not find a remote method named: '{namespace}.{TypeAdapter(RPCMethodName).validate_python(add_me.__name__)}'"
        in f"{exec_info.value}"
    )


async def test_replier_not_started(
    rpc_client: RabbitMQRPCClient, namespace: RPCNamespace
):
    async with rpc_server_lfespan(rpc_client):
        await _assert_event_not_registered(rpc_client, namespace)


async def test_replier_handler_not_registered(
    rpc_client: RabbitMQRPCClient,
    rpc_server: RabbitMQRPCClient,
    namespace: RPCNamespace,
):
    async with rpc_server_lfespan(rpc_client):
        await _assert_event_not_registered(rpc_client, namespace)


async def test_request_is_missing_arguments(
    rpc_client: RabbitMQRPCClient,
    rpc_server: RabbitMQRPCClient,
    namespace: RPCNamespace,
):
    await rpc_server.register_handler(
        namespace, TypeAdapter(RPCMethodName).validate_python(add_me.__name__), add_me
    )

    async with rpc_server_lfespan(rpc_client), rpc_server_lfespan(rpc_server):
        # missing 1 argument
        # with pytest.raises(TypeError) as exec_info:
        await rpc_client.request(
            namespace,
            TypeAdapter(RPCMethodName).validate_python(add_me.__name__),
            x=1,
        )
        # assert (
        #     f"{TypeAdapter(RPCMethodName).validate_python(add_me.__name__)}() missing 1 required keyword-only argument: 'y'"
        #     in f"{exec_info.value}"
        # )

        # missing all arguments
        with pytest.raises(TypeError) as exec_info:
            await rpc_client.request(
                namespace, TypeAdapter(RPCMethodName).validate_python(add_me.__name__)
            )
        assert (
            f"{TypeAdapter(RPCMethodName).validate_python(add_me.__name__)}() missing 2 required keyword-only arguments: 'x' and 'y'"
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
        namespace,
        TypeAdapter(RPCMethodName).validate_python(_long_running.__name__),
        _long_running,
    )

    async with rpc_server_lfespan(rpc_client), rpc_server_lfespan(rpc_server):
        with pytest.raises(asyncio.TimeoutError):
            await rpc_client.request(
                namespace,
                TypeAdapter(RPCMethodName).validate_python(_long_running.__name__),
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
        namespace,
        TypeAdapter(RPCMethodName).validate_python(_raising_error.__name__),
        _raising_error,
    )

    async with rpc_server_lfespan(rpc_client), rpc_server_lfespan(rpc_server):
        with pytest.raises(RuntimeError) as exec_info:
            await rpc_client.request(
                namespace,
                TypeAdapter(RPCMethodName).validate_python(_raising_error.__name__),
            )
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
            namespace, TypeAdapter(RPCMethodName).validate_python("a_name"), _get_custom
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
                namespace,
                TypeAdapter(RPCMethodName).validate_python("a_name"),
                x=10,
                timeout_s=1,
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

    await rpc_server.register_handler(
        namespace, TypeAdapter(RPCMethodName).validate_python("same_name"), _a_handler
    )
    with pytest.raises(RuntimeError) as exec_info:
        await rpc_server.register_handler(
            namespace,
            TypeAdapter(RPCMethodName).validate_python("same_name"),
            _another_handler,
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
                RPCNamespace("a"),
                TypeAdapter(RPCMethodName).validate_python(handler_name),
                _a_handler,
            )
    else:
        await rpc_server.register_handler(
            RPCNamespace("a"),
            TypeAdapter(RPCMethodName).validate_python(handler_name),
            _a_handler,
        )
