# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_webserver.wallets import WalletPaymentCreated
from pydantic import parse_obj_as
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from respx import MockRouter
from servicelib.rabbitmq import RabbitMQRPCClient, RPCMethodName, RPCServerError
from simcore_service_payments.api.rpc.routes import PAYMENTS_RPC_NAMESPACE
from simcore_service_payments.core.errors import PaymentNotFoundError

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    rabbit_env_vars_dict: EnvVarsDict,  # rabbitMQ settings from 'rabbit' service
    postgres_env_vars_dict: EnvVarsDict,
    wait_for_postgres_ready_and_db_migrated: None,
    external_environment: EnvVarsDict,
):
    # set environs
    monkeypatch.delenv("PAYMENTS_RABBITMQ", raising=False)
    monkeypatch.delenv("PAYMENTS_POSTGRES", raising=False)

    return setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            **rabbit_env_vars_dict,
            **postgres_env_vars_dict,
            **external_environment,
            "POSTGRES_CLIENT_NAME": "payments-service-pg-client",
        },
    )


@pytest.fixture
def init_payment_kwargs(faker: Faker) -> dict[str, Any]:
    return {
        "amount_dollars": 999999.99609375,  # SEE https://github.com/ITISFoundation/appmotion-exchange/issues/2
        "target_credits": 100,
        "product_name": "osparc",
        "wallet_id": 1,
        "wallet_name": "wallet-name",
        "user_id": 1,
        "user_name": "user",
        "user_email": "user@email.com",
    }


async def test_rpc_init_payment_fail(
    app: FastAPI,
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
    init_payment_kwargs: dict[str, Any],
):
    assert app
    rpc_client = await rabbitmq_rpc_client("web-server-client")

    with pytest.raises(RPCServerError) as exc_info:
        await rpc_client.request(
            PAYMENTS_RPC_NAMESPACE,
            parse_obj_as(RPCMethodName, "init_payment"),
            **init_payment_kwargs,
        )

    exc = exc_info.value
    assert exc.exc_type == f"{httpx.ConnectError}"
    assert exc.method_name == "init_payment"
    assert exc.msg


async def test_webserver_one_time_payment_workflow(
    app: FastAPI,
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
    mock_payments_gateway_service_or_none: MockRouter | None,
    init_payment_kwargs: dict[str, Any],
):
    assert app

    rpc_client = await rabbitmq_rpc_client("web-server-client")

    result = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "init_payment"),
        **init_payment_kwargs,
    )

    assert isinstance(result, WalletPaymentCreated)

    if mock_payments_gateway_service_or_none:
        assert mock_payments_gateway_service_or_none.routes["init_payment"].called

    result = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "cancel_payment"),
        payment_id=result.payment_id,
        user_id=init_payment_kwargs["user_id"],
        wallet_id=init_payment_kwargs["wallet_id"],
    )

    assert result is None

    if mock_payments_gateway_service_or_none:
        assert mock_payments_gateway_service_or_none.routes["cancel_payment"].called


async def test_cancel_invalid_payment_id(
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
    mock_payments_gateway_service_or_none: MockRouter | None,
    init_payment_kwargs: dict[str, Any],
    faker: Faker,
):
    invalid_payment_id = faker.uuid4()

    rpc_client = await rabbitmq_rpc_client("web-server-client")

    with pytest.raises(PaymentNotFoundError):
        await rpc_client.request(
            PAYMENTS_RPC_NAMESPACE,
            parse_obj_as(RPCMethodName, "cancel_payment"),
            payment_id=invalid_payment_id,
            user_id=init_payment_kwargs["user_id"],
            wallet_id=init_payment_kwargs["wallet_id"],
        )
