# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from models_library.api_schemas_webserver.wallets import PaymentMethodID
from models_library.basic_types import IDStr
from models_library.payments import UserInvoiceAddress
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import EmailStr
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from respx import MockRouter
from simcore_service_payments.db.payments_methods_repo import PaymentsMethodsRepo
from simcore_service_payments.db.payments_transactions_repo import (
    PaymentsTransactionsRepo,
)
from simcore_service_payments.models.db import PaymentsMethodsDB
from simcore_service_payments.services import payments
from simcore_service_payments.services.notifier import NotifierService
from simcore_service_payments.services.notifier_email import EmailProvider
from simcore_service_payments.services.notifier_ws import WebSocketProvider
from simcore_service_payments.services.payments_gateway import PaymentsGatewayApi
from simcore_service_payments.services.resource_usage_tracker import (
    ResourceUsageTrackerApi,
)

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    with_disabled_rabbitmq_and_rpc: None,
    postgres_env_vars_dict: EnvVarsDict,
    wait_for_postgres_ready_and_db_migrated: None,
):
    # set environs
    monkeypatch.delenv("PAYMENTS_RABBITMQ", raising=False)
    monkeypatch.delenv("PAYMENTS_POSTGRES", raising=False)

    return setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            **postgres_env_vars_dict,
            "POSTGRES_CLIENT_NAME": "payments-service-pg-client",
        },
    )


@pytest.fixture
def mock_email_provider(mocker: MockerFixture) -> MagicMock:
    mock = mocker.MagicMock(EmailProvider)
    mock.get_name.return_value = EmailProvider.get_name()
    return mock


@pytest.fixture
def mock_ws_provider(mocker: MockerFixture) -> MagicMock:
    mock = mocker.MagicMock(WebSocketProvider)
    mock.get_name.return_value = WebSocketProvider.get_name()
    return mock


async def test_fails_to_pay_with_payment_method_without_funds(
    app: FastAPI,
    create_fake_payment_method_in_db: Callable[
        [PaymentMethodID, WalletID, UserID], Awaitable[PaymentsMethodsDB]
    ],
    no_funds_payment_method_id: PaymentMethodID,
    mock_payments_gateway_service_or_none: MockRouter | None,
    wallet_id: WalletID,
    wallet_name: IDStr,
    user_id: UserID,
    user_name: IDStr,
    user_email: EmailStr,
    payments_clean_db: None,
    mocker: MockerFixture,
    mock_email_provider: MagicMock,
    mock_ws_provider: MagicMock,
):
    if mock_payments_gateway_service_or_none is None:
        pytest.skip(
            "cannot run thist test against external because it setup a payment method"
        )

    payment_method_without_funds = await create_fake_payment_method_in_db(
        payment_method_id=no_funds_payment_method_id,
        wallet_id=wallet_id,
        user_id=user_id,
    )

    rut = ResourceUsageTrackerApi.get_from_app_state(app)
    rut_create_credit_transaction = mocker.spy(rut, "create_credit_transaction")

    # Mocker providers
    notifier = NotifierService(mock_email_provider, mock_ws_provider)

    payment = await payments.pay_with_payment_method(
        gateway=PaymentsGatewayApi.get_from_app_state(app),
        rut=rut,
        repo_transactions=PaymentsTransactionsRepo(db_engine=app.state.engine),
        repo_methods=PaymentsMethodsRepo(db_engine=app.state.engine),
        notifier=notifier,
        #
        payment_method_id=payment_method_without_funds.payment_method_id,
        amount_dollars=100,
        target_credits=100,
        product_name="my_product",
        wallet_id=wallet_id,
        wallet_name=wallet_name,
        user_id=user_id,
        user_name=user_name,
        user_email=user_email,
        user_address=UserInvoiceAddress(country="CH"),
        stripe_price_id="stripe-id",
        stripe_tax_rate_id="stripe-id",
        comment="test_failure_in_pay_with_payment_method",
    )

    # should not add credits
    assert not rut_create_credit_transaction.called

    # check resulting payment
    assert payment.completed_at is not None
    assert payment.created_at < payment.completed_at
    assert payment.state == "FAILED"
    assert payment.state_message, "expected reason of failure"

    # check notifications triggered as background tasks
    await asyncio.sleep(0.1)
    assert len(notifier._background_tasks) == 0  # noqa: SLF001

    assert mock_email_provider.notify_payment_completed.called
    assert (
        mock_email_provider.notify_payment_completed.call_args.kwargs["user_id"]
        == user_id
    )
    assert (
        mock_email_provider.notify_payment_completed.call_args.kwargs["payment"]
        == payment
    )

    # Websockets notification should be in the exclude list
    assert not mock_ws_provider.notify_payment_completed.called
