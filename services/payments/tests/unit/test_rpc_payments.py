# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import Awaitable, Callable

import httpx
import pytest
from fastapi import FastAPI
from models_library.api_schemas_webserver.wallets import WalletPaymentCreated
from pydantic import parse_obj_as
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from respx import MockRouter
from servicelib.rabbitmq import RabbitMQRPCClient, RPCMethodName, RPCServerError
from simcore_service_payments.api.rpc.routes import PAYMENTS_RPC_NAMESPACE

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    rabbit_env_vars_dict: EnvVarsDict,  # rabbitMQ settings from 'rabbit' service
):
    monkeypatch.delenv("PAYMENTS_RABBITMQ", raising=False)
    return setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            **rabbit_env_vars_dict,
        },
    )


async def test_rpc_create_payment_fail(
    app: FastAPI,
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
):
    rpc_client = await rabbitmq_rpc_client("web-server-client")

    with pytest.raises(RPCServerError) as exc_info:
        await rpc_client.request(
            PAYMENTS_RPC_NAMESPACE,
            parse_obj_as(RPCMethodName, "create_payment"),
            amount_dollars=100,
            target_credits=100,
            product_name="osparc",
            wallet_id=1,
            wallet_name="wallet-name",
            user_id=1,
            user_name="user-name",
            user_email="user-name@email.com",
        )

    exc = exc_info.value
    assert exc.exc_type == httpx.ConnectError
    assert exc.method_name == "create_payment"
    assert exc.msg


async def test_webserver_one_time_payment_workflow(
    app: FastAPI,
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
    mock_payments_gateway_service_api_base: MockRouter,
    mock_init_payment_route: Callable,
):
    mock_init_payment_route(mock_payments_gateway_service_api_base)

    rpc_client = await rabbitmq_rpc_client("web-server-client")

    result = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "create_payment"),
        amount_dollars=100,
        target_credits=100,
        product_name="osparc",
        wallet_id=1,
        wallet_name="wallet-name",
        user_id=1,
        user_name="user-name",
        user_email="user-name@email.com",
    )

    assert isinstance(result, WalletPaymentCreated)
