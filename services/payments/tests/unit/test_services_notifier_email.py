# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import respx
from faker import Faker
from fastapi import status
from jinja2 import DictLoader, Environment, select_autoescape
from models_library.products import ProductName
from models_library.users import UserID
from pydantic import EmailStr
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.email import SMTPSettings
from simcore_postgres_database.models.products import Vendor
from simcore_service_payments.db.payment_users_repo import PaymentsUsersRepo
from simcore_service_payments.models.db import PaymentsTransactionsDB
from simcore_service_payments.services.notifier_email import (
    _PRODUCT_NOTIFICATIONS_TEMPLATES,
    EmailProvider,
    _create_email_session,
    _create_user_email,
    _PaymentData,
    _ProductData,
    _UserData,
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
def smtp_mock_or_none(
    mocker: MockerFixture,
    is_external_user_email: bool,
    user_email: EmailStr,
) -> MagicMock | None:
    if not is_external_user_email:
        return mocker.patch("simcore_service_payments.services.notifier_email.SMTP")
    print("🚨 Emails might be sent to", f"{user_email=}")
    return None


@pytest.fixture(params=["ok", "ko"])
def mocked_get_invoice_pdf_response(
    request: pytest.FixtureRequest,
    respx_mock: respx.MockRouter,
    transaction: PaymentsTransactionsDB,
) -> respx.MockRouter:
    if request.param == "ok":
        file_name = "test-attachment.pdf"
        file_content = b"%PDF-1.4 ... (file content here) ..."

        response = httpx.Response(
            status.HTTP_200_OK,
            content=file_content,
            headers={
                "Content-Type": "application/pdf",
                "Content-Disposition": f'attachment; filename="{file_name}"',
            },
        )
    else:
        assert request.param == "ko"
        response = httpx.Response(
            status.HTTP_404_NOT_FOUND,
            text=f"{request.fixturename} is set to '{request.param}'",
        )

    respx_mock.get(f"{transaction.invoice_pdf_url}").mock(return_value=response)

    return respx_mock


@pytest.fixture
def transaction(
    faker: Faker, successful_transaction: dict[str, Any]
) -> PaymentsTransactionsDB:
    kwargs = {
        k: successful_transaction[k]
        for k in PaymentsTransactionsDB.model_fields
        if k in successful_transaction
    }
    return PaymentsTransactionsDB(**kwargs)


async def test_send_email_workflow(
    app_environment: EnvVarsDict,
    faker: Faker,
    transaction: PaymentsTransactionsDB,
    user_email: EmailStr,
    product_name: ProductName,
    product: dict[str, Any],
    smtp_mock_or_none: MagicMock | None,
    mocked_get_invoice_pdf_response: respx.MockRouter,
):
    """
    Example of usage with external email and envfile

        > pytest --faker-user-email=me@email.me --external-envfile=.myenv -k test_send_email_workflow  --pdb tests/unit
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
    mocked_get_invoice_pdf_response: respx.MockRouter,
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

    if smtp_mock_or_none:
        assert smtp_mock_or_none.called
