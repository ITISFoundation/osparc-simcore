# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import Awaitable, Callable

import orjson
import pytest
from fastapi import FastAPI
from models_library.api_schemas_webserver.wallets import WalletPaymentCreated
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from servicelib.rabbitmq import RabbitMQRPCClient, RPCMethodName
from simcore_service_payments.api.rpc._payments import create_payment
from simcore_service_payments.services.rabbitmq import PAYMENTS_RPC_NAMESPACE

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


async def test_webserver_one_time_payment_workflow(
    app: FastAPI,
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
):
    rpc_client = await rabbitmq_rpc_client("web-server-client")

    kwargs = {
        "amount_dollars": 100,
        "target_credits": 100,
        "product_name": "osparc",
        "wallet_id": 1,
        "wallet_name": "wallet-name",
        "user_id": 1,
        "user_name": "user-name",
        "user_email": "user-name@email.com",
    }

    json_result = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE, RPCMethodName(create_payment.__name__), **kwargs
    )
    assert isinstance(json_result, bytes)
    result = orjson.loads(json_result)

    WalletPaymentCreated.parse_obj(result)
