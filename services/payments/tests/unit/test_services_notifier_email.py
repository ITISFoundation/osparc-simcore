# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from faker import Faker
from jinja2 import DictLoader, Environment, select_autoescape
from models_library.products import ProductName
from models_library.users import UserID
from pydantic import EmailStr, parse_obj_as
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from settings_library.email import SMTPSettings
from simcore_postgres_database.models.products import Vendor
from simcore_service_payments.db.payment_users_repo import PaymentsUsersRepo
from simcore_service_payments.models.db import PaymentsTransactionsDB
from simcore_service_payments.services.notifier_email import (
    _PRODUCT_NOTIFICATIONS_TEMPLATES,
    EmailProvider,
    _add_attachments,
    _create_email_session,
    _create_user_email,
    _PaymentData,
    _ProductData,
    _UserData,
)


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    external_environment: EnvVarsDict,
    docker_compose_service_payments_env_vars: EnvVarsDict,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **docker_compose_service_payments_env_vars,
            **external_environment,
        },
    )


@pytest.fixture(scope="session")
def external_email(request: pytest.FixtureRequest) -> str | None:
    email_or_none = request.config.getoption("--external-email", default=None)
    return parse_obj_as(EmailStr, email_or_none) if email_or_none else None


@pytest.fixture
def user_email(user_email: EmailStr, external_email: EmailStr | None) -> EmailStr:
    if external_email:
        print("📧 EXTERNAL using in test", f"{external_email=}")
        return external_email
    return user_email


@pytest.fixture
def smtp_mock_or_none(
    mocker: MockerFixture, external_email: EmailStr | None
) -> MagicMock | None:
    if not external_email:
        return mocker.patch("simcore_service_payments.services.notifier_email.SMTP")
    return None


@pytest.fixture
def mock_get_invoice(mocker: MockerFixture) -> MagicMock:
    _mock_get_invoice = mocker.patch(
        "simcore_service_payments.services.notifier_email._get_invoice_pdf"
    )
    _mock_get_invoice.return_value = None
    return _mock_get_invoice


@pytest.fixture
def transaction(
    faker: Faker, successful_transaction: dict[str, Any]
) -> PaymentsTransactionsDB:
    kwargs = {
        k: successful_transaction[k]
        for k in PaymentsTransactionsDB.__fields__
        if k in successful_transaction
    }
    return PaymentsTransactionsDB(**kwargs)


async def test_send_email_workflow(
    app_environment: EnvVarsDict,
    tmp_path: Path,
    faker: Faker,
    transaction: PaymentsTransactionsDB,
    external_email: str | None,
    user_email: EmailStr,
    product_name: ProductName,
    product: dict[str, Any],
    smtp_mock_or_none: MagicMock | None,
    mock_get_invoice: MagicMock,
):
    """
    Example of usage with external email and envfile

        > pytest --external-email=me@email.me --external-envfile=.myenv -k test_send_email_workflow  --pdb tests/unit
    """

    settings = SMTPSettings.create_from_envs()
    env = Environment(
        loader=DictLoader(_PRODUCT_NOTIFICATIONS_TEMPLATES),
        autoescape=select_autoescape(["html", "xml"]),
    )

    user_data = _UserData(
        first_name=faker.first_name(),
        last_name=faker.last_name(),
        email=user_email,
    )

    vendor: Vendor = product["vendor"]

    product_data = _ProductData(  # type: ignore
        product_name=product_name,
        display_name=product["display_name"],
        vendor_display_inline=f"{vendor.get('name','')}, {vendor.get('address','')}",
        support_email=product["support_email"],
    )

    payment_data = _PaymentData(
        price_dollars=f"{transaction.price_dollars:.2f}",
        osparc_credits=f"{transaction.osparc_credits:.2f}",
        invoice_url=transaction.invoice_url,
        invoice_pdf_url=transaction.invoice_pdf_url,
    )

    msg = await _create_user_email(env, user_data, payment_data, product_data)

    attachment = tmp_path / "test-attachment.txt"
    attachment.write_text(faker.text())
    _add_attachments(msg, [attachment])

    async with _create_email_session(settings) as smtp:
        await smtp.send_message(msg)

    if smtp_mock_or_none:
        assert smtp_mock_or_none.called
        assert isinstance(smtp, AsyncMock)
        assert smtp.login.called
        assert smtp.send_message.called


async def test_email_provider(
    app_environment: EnvVarsDict,
    mocker: MockerFixture,
    user_id: UserID,
    user_first_name: str,
    user_last_name: str,
    user_email: EmailStr,
    product_name: ProductName,
    product: dict[str, Any],
    transaction: PaymentsTransactionsDB,
    smtp_mock_or_none: MagicMock | None,
    mock_get_invoice: MagicMock,
):
    settings = SMTPSettings.create_from_envs()

    # mock access to db
    users_repo = PaymentsUsersRepo(MagicMock())
    get_notification_data_mock = mocker.patch.object(
        users_repo,
        "get_notification_data",
        return_value=SimpleNamespace(
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

    provider = EmailProvider(settings, users_repo)

    await provider.notify_payment_completed(user_id=user_id, payment=transaction)
    assert get_notification_data_mock.called
    assert mock_get_invoice.called

    if smtp_mock_or_none:
        assert smtp_mock_or_none.called
