# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from faker import Faker
from models_library.products import ProductName
from models_library.users import UserID
from pydantic import EmailStr
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_payments.db.payment_users_repo import PaymentsUsersRepo
from simcore_service_payments.models.db import PaymentsTransactionsDB
from simcore_service_payments.services.notifier_email import (
    EmailProvider,
)


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    external_envfile_dict: EnvVarsDict,
    docker_compose_service_environment_dict: EnvVarsDict,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **docker_compose_service_environment_dict,
            **external_envfile_dict,
        },
    )


@pytest.fixture
def transaction(faker: Faker, successful_transaction: dict[str, Any]) -> PaymentsTransactionsDB:
    valid_keys = successful_transaction.keys() & PaymentsTransactionsDB.model_fields.keys()
    return PaymentsTransactionsDB(**{k: successful_transaction[k] for k in valid_keys})


@pytest.fixture
def mock_rabbitmq_rpc_client() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_send_message_from_template(mocker: MockerFixture) -> AsyncMock:
    return mocker.patch(
        "simcore_service_payments.services.notifier_email.send_message_from_template",
        return_value=AsyncMock(),
    )


async def test_email_provider_sends_on_success(
    app_environment: EnvVarsDict,
    mocker: MockerFixture,
    user_id: UserID,
    user_first_name: str,
    user_last_name: str,
    user_email: EmailStr,
    product_name: ProductName,
    product: dict[str, Any],
    transaction: PaymentsTransactionsDB,
    mock_rabbitmq_rpc_client: AsyncMock,
    mock_send_message_from_template: AsyncMock,
):
    users_repo = PaymentsUsersRepo(MagicMock())
    mocker.patch.object(
        users_repo,
        "get_notification_data",
        return_value=MagicMock(
            payment_id=transaction.payment_id,
            first_name=user_first_name,
            last_name=user_last_name,
            email=user_email,
            product_name=product_name,
            display_name=product["display_name"],
            vendor=product["vendor"],
            support_email=product["support_email"],
        ),
    )

    provider = EmailProvider(mock_rabbitmq_rpc_client, users_repo)

    await provider.notify_payment_completed(user_id=user_id, payment=transaction)

    assert mock_send_message_from_template.called

    call_kwargs = mock_send_message_from_template.call_args
    assert call_kwargs.kwargs["template_ref"].template_name == "paid"
    assert call_kwargs.kwargs["context"]["payment"]["price_dollars"] == f"{transaction.price_dollars:.2f}"
    assert call_kwargs.kwargs["context"]["payment"]["osparc_credits"] == f"{transaction.osparc_credits:.2f}"


async def test_email_provider_skips_non_success(
    app_environment: EnvVarsDict,
    faker: Faker,
    user_id: UserID,
    mock_rabbitmq_rpc_client: AsyncMock,
    mock_send_message_from_template: AsyncMock,
):
    users_repo = PaymentsUsersRepo(MagicMock())
    provider = EmailProvider(mock_rabbitmq_rpc_client, users_repo)

    pending_transaction = PaymentsTransactionsDB(
        payment_id=f"pt_{faker.pyint()}",
        price_dollars=faker.pydecimal(left_digits=3, right_digits=2, positive=True),
        osparc_credits=faker.pydecimal(left_digits=3, right_digits=2, positive=True),
        product_name="osparc",
        user_id=user_id,
        user_email=faker.email(),
        wallet_id=faker.pyint(),
        comment=None,
        invoice_url=None,
        stripe_invoice_id=None,
        invoice_pdf_url=None,
        initiated_at=faker.date_time(),
        completed_at=None,
        state="PENDING",
        state_message=None,
    )

    await provider.notify_payment_completed(user_id=user_id, payment=pending_transaction)

    assert not mock_send_message_from_template.called


async def test_email_provider_logs_on_rpc_failure(
    app_environment: EnvVarsDict,
    mocker: MockerFixture,
    user_id: UserID,
    user_first_name: str,
    user_last_name: str,
    user_email: EmailStr,
    product_name: ProductName,
    product: dict[str, Any],
    transaction: PaymentsTransactionsDB,
    mock_rabbitmq_rpc_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
):
    users_repo = PaymentsUsersRepo(MagicMock())
    mocker.patch.object(
        users_repo,
        "get_notification_data",
        return_value=MagicMock(
            payment_id=transaction.payment_id,
            first_name=user_first_name,
            last_name=user_last_name,
            email=user_email,
            product_name=product_name,
            display_name=product["display_name"],
            vendor=product["vendor"],
            support_email=product["support_email"],
        ),
    )

    mocker.patch(
        "simcore_service_payments.services.notifier_email.send_message_from_template",
        side_effect=RuntimeError("RPC connection failed"),
    )

    provider = EmailProvider(mock_rabbitmq_rpc_client, users_repo)

    with caplog.at_level(logging.ERROR):
        await provider.notify_payment_completed(user_id=user_id, payment=transaction)

    assert "Failed to send payment completed email notification" in caplog.text
