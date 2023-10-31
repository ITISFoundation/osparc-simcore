# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from collections.abc import Awaitable, Callable

import pytest
from faker import Faker
from models_library.rabbitmq_basic_types import RPCMethodName
from servicelib.rabbitmq import RabbitMQRPCClient, RPCNamespace, RPCRouter

pytest_simcore_core_services_selection = [
    "rabbit",
]


router = RPCRouter()


@router.expose()
async def a_str_method(
    a_global_arg: str, *, a_global_kwarg: str, a_specific_kwarg: str
) -> str:
    return f"{a_global_arg}, that was a winner! {a_global_kwarg} {a_specific_kwarg}"


@router.expose()
async def an_int_method(a_global_arg: str, *, a_global_kwarg: str) -> int:
    return 34


@router.expose()
async def a_raising_method(a_global_arg: str, *, a_global_kwarg: str) -> int:
    msg = "This is not good!"
    raise RuntimeError(msg)


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

    with pytest.raises(RuntimeError):
        await rpc_client.request(
            router_namespace,
            RPCMethodName(a_raising_method.__name__),
        )
