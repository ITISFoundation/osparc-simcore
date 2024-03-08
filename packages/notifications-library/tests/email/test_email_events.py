# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
"""
These tests can be run against external configuration

cd packages/notifications-library
pytest --external-envfile=.my-env --external-support-email=support@email.com  --external-user-email=my@email.com tests/email

"""


from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from faker import Faker
from jinja2 import StrictUndefined
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


@pytest.fixture
def event_extra_data(
    event_name: str, faker: Faker, product_name: ProductName, payment_data: PaymentData
) -> dict[str, Any]:

    match event_name:
        case "on_registered":
            return {
                "host": f"https://{product_name}.io",
                "link": faker.image_url(width=640, height=480),
            }
        case "on_new_code":
            return {
                "host": f"https://{product_name}.io",
                "code": faker.pystr_format(string_format="####", letters=""),
            }
        case "on_reset_password":
            return {
                "host": f"https://{product_name}.io",
                "link": faker.image_url(width=640, height=480),
            }
        case "on_payed":
            return {
                "payment": payment_data,
            }

        case _:
            return {}


@pytest.fixture
def event_attachments(event_name: str, faker: Faker, tmp_path: Path) -> list[Path]:
    paths = []
    match event_name:
        case "on_payed":
            paths.append(tmp_path / "test-payed-invoice.pdf")

    # fill with fake data
    for p in paths:
        p.write_text(faker.text())
    return paths


@pytest.mark.parametrize(
    "event_name",
    [
        "on_new_code",
        "on_registered",
        "on_reset_password",
        "on_payed",
    ],
)
async def test_email_event(
    app_environment: EnvVarsDict,
    smtp_mock_or_none: MagicMock | None,
    user_data: UserData,
    user_email: EmailStr,
    product_data: ProductData,
    product_name: ProductName,
    event_name: str,
    event_extra_data: dict[str, Any],
    event_attachments: list[Path],
):
    assert user_data.email == user_email
    assert product_data.product_name == product_name

    parts = render_email_parts(
        env=create_render_env_from_package(undefined=StrictUndefined),
        event_name=event_name,
        user=user_data,
        product=product_data,
        # extras
        **event_extra_data,
    )
    assert parts.from_.addr_spec == product_data.support_email
    assert parts.to.addr_spec == user_email

    msg = compose_email(*parts)
    if event_attachments:
        add_attachments(msg, event_attachments)

    async with create_email_session(settings=SMTPSettings.create_from_envs()) as smtp:
        await smtp.send_message(msg)

    # check email was sent
    if smtp_mock_or_none:
        assert smtp_mock_or_none.called
        assert isinstance(smtp, AsyncMock)
        assert smtp.login.called
        assert smtp.send_message.called
