# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any

import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_payments.errors import PaymentNotFoundError
from models_library.api_schemas_webserver.wallets import WalletPaymentInitiated
from models_library.payments import UserInvoiceAddress
from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import TypeAdapter
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from respx import MockRouter
from servicelib.rabbitmq import RabbitMQRPCClient, RPCServerError
from servicelib.rabbitmq._constants import RPC_REQUEST_DEFAULT_TIMEOUT_S
from simcore_service_payments.api.rpc.routes import PAYMENTS_RPC_NAMESPACE

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
    external_envfile_dict: EnvVarsDict,
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
            **external_envfile_dict,
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
        "user_address": UserInvoiceAddress(country="CH"),
        "stripe_price_id": "stripe-price-id",
        "stripe_tax_rate_id": "stripe-tax-rate-id",
    }


async def test_rpc_init_payment_fail(
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    init_payment_kwargs: dict[str, Any],
    payments_clean_db: None,
):
    assert app

    with pytest.raises(RPCServerError) as exc_info:
        await rpc_client.request(
            PAYMENTS_RPC_NAMESPACE,
            TypeAdapter(RPCMethodName).validate_python("init_payment"),
            **init_payment_kwargs,
        )

    error = exc_info.value
    assert isinstance(error, RPCServerError)
    assert error.exc_type == "httpx.ConnectError"
    assert error.method_name == "init_payment"
    assert error.exc_message
    assert error.traceback


async def test_webserver_one_time_payment_workflow(
    is_pdb_enabled: bool,
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    mock_payments_gateway_service_or_none: MockRouter | None,
    init_payment_kwargs: dict[str, Any],
    payments_clean_db: None,
):
    assert app

    result = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("init_payment"),
        **init_payment_kwargs,
    )

    assert isinstance(result, WalletPaymentInitiated)

    if mock_payments_gateway_service_or_none:
        assert mock_payments_gateway_service_or_none.routes["init_payment"].called

    result = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("cancel_payment"),
        payment_id=result.payment_id,
        user_id=init_payment_kwargs["user_id"],
        wallet_id=init_payment_kwargs["wallet_id"],
        timeout_s=None if is_pdb_enabled else RPC_REQUEST_DEFAULT_TIMEOUT_S,
    )

    assert result is None

    if mock_payments_gateway_service_or_none:
        assert mock_payments_gateway_service_or_none.routes["cancel_payment"].called


async def test_cancel_invalid_payment_id(
    is_pdb_enabled: bool,
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    mock_payments_gateway_service_or_none: MockRouter | None,
    init_payment_kwargs: dict[str, Any],
    faker: Faker,
    payments_clean_db: None,
):
    invalid_payment_id = faker.uuid4()

    with pytest.raises(PaymentNotFoundError) as exc_info:
        await rpc_client.request(
            PAYMENTS_RPC_NAMESPACE,
            TypeAdapter(RPCMethodName).validate_python("cancel_payment"),
            payment_id=invalid_payment_id,
            user_id=init_payment_kwargs["user_id"],
            wallet_id=init_payment_kwargs["wallet_id"],
            timeout_s=None if is_pdb_enabled else RPC_REQUEST_DEFAULT_TIMEOUT_S,
        )
    error = exc_info.value
    assert isinstance(error, PaymentNotFoundError)
