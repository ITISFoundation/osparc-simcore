# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from collections.abc import Awaitable, Callable

import pytest
from faker import Faker
from models_library.rabbitmq_basic_types import RPCMethodName
from servicelib.rabbitmq import (
    RabbitMQRPCClient,
    RPCNamespace,
    RPCRouter,
    RPCServerError,
)

pytest_simcore_core_services_selection = [
    "rabbit",
]


router = RPCRouter()


class MyBaseError(Exception): ...


class MyExpectedError(MyBaseError): ...


@router.expose()
async def a_str_method(
    a_global_arg: str, *, a_global_kwarg: str, a_specific_kwarg: str
) -> str:
    return f"{a_global_arg}, that was a winner! {a_global_kwarg} {a_specific_kwarg}"


@router.expose()
async def an_int_method(a_global_arg: str, *, a_global_kwarg: str) -> int:
    return 34


@router.expose(reraise_if_error_type=(MyBaseError,))
async def raising_expected_error(a_global_arg: str, *, a_global_kwarg: str) -> int:
    msg = "This could happen"
    raise MyExpectedError(msg)


@router.expose()
async def raising_unexpected_error(a_global_arg: str, *, a_global_kwarg: str) -> int:
    msg = "This is not good!"
    raise ValueError(msg)


@pytest.fixture
def router_namespace(faker: Faker) -> RPCNamespace:
    return faker.pystr()


async def test_exposed_methods(
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
    router_namespace: RPCNamespace,
):
    rpc_client = await rabbitmq_rpc_client("client")
    rpc_server = await rabbitmq_rpc_client("server")

    a_arg = "The A-Team"
    a_kwargs = "What about McGiver?"
    a_specific_kwarg = "Yeah, it was actually good, too!"

    await rpc_server.register_router(
        router, router_namespace, a_arg, a_global_kwarg=a_kwargs
    )

    rpc_result = await rpc_client.request(
        router_namespace,
        RPCMethodName(a_str_method.__name__),
        a_specific_kwarg=a_specific_kwarg,
    )
    assert isinstance(rpc_result, str)
    result = rpc_result
    assert result == f"{a_arg}, that was a winner! {a_kwargs} {a_specific_kwarg}"

    rpc_result = await rpc_client.request(
        router_namespace,
        RPCMethodName(an_int_method.__name__),
    )
    assert isinstance(rpc_result, int)
    result = rpc_result
    assert result == 34

    # unexpected errors are turned into RPCServerError
    with pytest.raises(RPCServerError) as exc_info:
        await rpc_client.request(
            router_namespace,
            RPCMethodName(raising_unexpected_error.__name__),
        )
    assert "This is not good!" in f"{exc_info.value}"
    assert "builtins.ValueError" in f"{exc_info.value}"

    # This error was classified int he interface
    with pytest.raises(MyBaseError) as exc_info:
        await rpc_client.request(
            router_namespace,
            RPCMethodName(raising_expected_error.__name__),
        )

    assert isinstance(exc_info.value, MyExpectedError)
