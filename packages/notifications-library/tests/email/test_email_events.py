# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
"""
These tests can be run against external configuration

cd packages/notifications-library
pytest --external-envfile=.my-env --external-support-email=support@email.com  --external-user-email=my@email.com tests/email

"""


from email.message import EmailMessage
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from faker import Faker
from models_library.products import ProductName
from notifications_library._email import (
    add_attachments,
    compose_email,
    create_email_session,
)
from notifications_library._email_render import render_email_parts
from notifications_library._models import ProductData, UserData
from notifications_library._render import create_render_env_from_package
from notifications_library.payments import PaymentData
from pydantic import EmailStr
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.email import SMTPSettings


async def _send_and_assert(msg: EmailMessage, smtp_mock_or_none: MagicMock | None):
    settings = SMTPSettings.create_from_envs()

    async with create_email_session(settings) as smtp:
        await smtp.send_message(msg)

    # check email was sent
    if smtp_mock_or_none:
        assert smtp_mock_or_none.called
        assert isinstance(smtp, AsyncMock)
        assert smtp.login.called
        assert smtp.send_message.called


async def test_on_payed_event(
    app_environment: EnvVarsDict,
    tmp_path: Path,
    faker: Faker,
    user_email: EmailStr,
    product_name: ProductName,
    smtp_mock_or_none: MagicMock | None,
    user_data: UserData,
    product_data: ProductData,
    payment_data: PaymentData,
):

    assert user_data.email == user_email
    assert product_data.product_name == product_name

    parts = render_email_parts(
        env=create_render_env_from_package(),
        event_name="on_payed",
        user=user_data,
        product=product_data,
        # extras
        payment=payment_data,
    )

    assert parts.from_.addr_spec == product_data.support_email
    assert parts.to.addr_spec == user_email

    msg = compose_email(*parts)

    attachment = tmp_path / "test-attachment.txt"
    attachment.write_text(faker.text())
    add_attachments(msg, [attachment])

    await _send_and_assert(msg, smtp_mock_or_none)


async def test_on_registered_event(
    app_environment: EnvVarsDict,
    tmp_path: Path,
    faker: Faker,
    user_email: EmailStr,
    product_name: ProductName,
    smtp_mock_or_none: MagicMock | None,
    user_data: UserData,
    product_data: ProductData,
):

    parts = render_email_parts(
        env=create_render_env_from_package(),
        event_name="on_registered",
        user=user_data,
        product=product_data,
        # extras
        host=f"https://{product_name}.io",
        link=faker.image_url(width=640, height=480),
    )

    await _send_and_assert(compose_email(*parts), smtp_mock_or_none)
