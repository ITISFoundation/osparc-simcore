# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_webserver.wallets import (
    PaymentMethodInitiated,
    PaymentTransaction,
)
from models_library.basic_types import IDStr
from models_library.payments import UserInvoiceAddress
from models_library.products import ProductName, StripePriceID, StripeTaxRateID
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import EmailStr, TypeAdapter
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from respx import MockRouter
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq._constants import RPC_REQUEST_DEFAULT_TIMEOUT_S
from simcore_service_payments.api.rpc.routes import PAYMENTS_RPC_NAMESPACE
from simcore_service_payments.db.payments_methods_repo import PaymentsMethodsRepo
from simcore_service_payments.db.payments_transactions_repo import (
    PaymentsTransactionsRepo,
)
from simcore_service_payments.models.db import (
    InitPromptAckFlowState,
    PaymentTransactionState,
)
from simcore_service_payments.models.schemas.acknowledgements import AckPaymentMethod
from simcore_service_payments.services.payments_methods import insert_payment_method

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


async def test_webserver_init_and_cancel_payment_method_workflow(
    is_pdb_enabled: bool,
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    mock_payments_gateway_service_or_none: MockRouter | None,
    user_id: UserID,
    user_name: IDStr,
    user_email: EmailStr,
    wallet_name: IDStr,
    wallet_id: WalletID,
    payments_clean_db: None,
):
    assert app

    initiated = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("init_creation_of_payment_method"),
        wallet_id=wallet_id,
        wallet_name=wallet_name,
        user_id=user_id,
        user_name=user_name,
        user_email=user_email,
    )

    assert isinstance(initiated, PaymentMethodInitiated)

    if mock_payments_gateway_service_or_none:
        assert mock_payments_gateway_service_or_none.routes[
            "init_payment_method"
        ].called

    cancelled = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("cancel_creation_of_payment_method"),
        payment_method_id=initiated.payment_method_id,
        user_id=user_id,
        wallet_id=wallet_id,
        timeout_s=None if is_pdb_enabled else RPC_REQUEST_DEFAULT_TIMEOUT_S,
    )

    assert cancelled is None

    if mock_payments_gateway_service_or_none:
        assert mock_payments_gateway_service_or_none.routes[
            "delete_payment_method"
        ].called


async def test_webserver_crud_payment_method_workflow(
    is_pdb_enabled: bool,
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    mock_payments_gateway_service_or_none: MockRouter | None,
    user_id: UserID,
    user_name: IDStr,
    user_email: EmailStr,
    wallet_name: IDStr,
    wallet_id: WalletID,
    payments_clean_db: None,
):
    assert app

    inited = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("init_creation_of_payment_method"),
        wallet_id=wallet_id,
        wallet_name=wallet_name,
        user_id=user_id,
        user_name=user_name,
        user_email=user_email,
    )

    assert isinstance(inited, PaymentMethodInitiated)

    if mock_payments_gateway_service_or_none:
        assert mock_payments_gateway_service_or_none.routes[
            "init_payment_method"
        ].called

    # Faking ACK----
    repo = PaymentsMethodsRepo(app.state.engine)
    await repo.update_ack_payment_method(
        inited.payment_method_id,
        completion_state=InitPromptAckFlowState.SUCCESS,
        state_message="FAKED ACK",
    )
    # -----

    listed = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("list_payment_methods"),
        user_id=user_id,
        wallet_id=wallet_id,
        timeout_s=None if is_pdb_enabled else RPC_REQUEST_DEFAULT_TIMEOUT_S,
    )
    assert len(listed) == 1

    if mock_payments_gateway_service_or_none:
        assert mock_payments_gateway_service_or_none.routes[
            "batch_get_payment_methods"
        ].called

    got = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_payment_method"),
        payment_method_id=inited.payment_method_id,
        user_id=user_id,
        wallet_id=wallet_id,
        timeout_s=None if is_pdb_enabled else RPC_REQUEST_DEFAULT_TIMEOUT_S,
    )
    assert got == listed[0]
    if mock_payments_gateway_service_or_none:
        assert mock_payments_gateway_service_or_none.routes["get_payment_method"].called

    await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("delete_payment_method"),
        payment_method_id=inited.payment_method_id,
        user_id=user_id,
        wallet_id=wallet_id,
        timeout_s=None if is_pdb_enabled else RPC_REQUEST_DEFAULT_TIMEOUT_S,
    )

    if mock_payments_gateway_service_or_none:
        assert mock_payments_gateway_service_or_none.routes[
            "delete_payment_method"
        ].called


async def test_webserver_pay_with_payment_method_workflow(
    is_pdb_enabled: bool,
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    mock_resoruce_usage_tracker_service_api: None,
    mock_payments_gateway_service_or_none: MockRouter | None,
    faker: Faker,
    product_name: ProductName,
    product_price_stripe_price_id: StripePriceID,
    product_price_stripe_tax_rate_id: StripeTaxRateID,
    user_id: UserID,
    user_name: IDStr,
    user_email: EmailStr,
    wallet_name: IDStr,
    wallet_id: WalletID,
    payments_clean_db: None,
):
    assert app

    # faking Payment method
    created = await insert_payment_method(
        repo=PaymentsMethodsRepo(app.state.engine),
        payment_method_id=faker.uuid4(),
        user_id=user_id,
        wallet_id=wallet_id,
        ack=AckPaymentMethod(success=True, message="Faked ACK"),
    )

    transaction = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("pay_with_payment_method"),
        payment_method_id=created.payment_method_id,
        amount_dollars=faker.pyint(),
        target_credits=faker.pyint(),
        product_name=product_name,
        wallet_id=wallet_id,
        wallet_name=wallet_name,
        user_id=user_id,
        user_name=user_name,
        user_email=user_email,
        user_address=UserInvoiceAddress(country="CH"),
        stripe_price_id=product_price_stripe_price_id,
        stripe_tax_rate_id=product_price_stripe_tax_rate_id,
        comment="Payment with stored credit-card",
    )

    assert isinstance(transaction, PaymentTransaction)
    assert transaction.payment_id
    assert transaction.state == "SUCCESS"

    payment = await PaymentsTransactionsRepo(app.state.engine).get_payment_transaction(
        transaction.payment_id, user_id=user_id, wallet_id=wallet_id
    )
    assert payment is not None
    assert payment.payment_id == transaction.payment_id
    assert payment.state == PaymentTransactionState.SUCCESS
    assert payment.comment == "Payment with stored credit-card"
