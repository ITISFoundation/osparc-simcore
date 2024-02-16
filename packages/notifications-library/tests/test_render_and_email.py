# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import notifications_library
import pytest
from faker import Faker
from jinja2 import Environment, PackageLoader, select_autoescape
from models_library.products import ProductName
from notifications_library._email import (
    add_attachments,
    compose_email,
    create_email_session,
)
from notifications_library._render import ProductData, UserData, render_email_parts
from notifications_library.payments import PaymentData
from pydantic import EmailStr, parse_obj_as
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from settings_library.email import SMTPSettings
from simcore_postgres_database.models.products import Vendor


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    env_devel_dict: EnvVarsDict,
    external_environment: EnvVarsDict,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **env_devel_dict,
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
        return mocker.patch("notifications_library._email.SMTP")
    return None


async def test_send_email_workflow(
    app_environment: EnvVarsDict,
    tmp_path: Path,
    faker: Faker,
    external_email: str | None,
    user_email: EmailStr,
    product_name: ProductName,
    product: dict[str, Any],
    smtp_mock_or_none: MagicMock | None,
):
    """
    Example of usage with external email and envfile

        > pytest --external-email=me@email.me --external-envfile=.myenv -k test_send_email_workflow  --pdb tests/unit
    """

    settings = SMTPSettings.create_from_envs()
    env = Environment(
        loader=PackageLoader(notifications_library.__name__, "templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )

    user_data = UserData(
        first_name=faker.first_name(),
        last_name=faker.last_name(),
        email=user_email,
    )

    vendor: Vendor = product["vendor"]

    product_data = ProductData(  # type: ignore
        product_name=product_name,
        display_name=product["display_name"],
        vendor_display_inline=f"{vendor.get('name','')}, {vendor.get('address','')}",
        support_email=product["support_email"],
    )

    payment_data = PaymentData(
        price_dollars="300.00",
        osparc_credits="1500",
        invoice_url="https://the-invoice.com",
    )

    msg = compose_email(
        *render_email_parts(
            env,
            template_prefix="notify_payments",
            user=user_data,
            product=product_data,
            extra={"payments": payment_data},
        )
    )

    attachment = tmp_path / "test-attachment.txt"
    attachment.write_text(faker.text())
    add_attachments(msg, [attachment])

    async with create_email_session(settings) as smtp:
        await smtp.send_message(msg)

    if smtp_mock_or_none:
        assert smtp_mock_or_none.called
        assert isinstance(smtp, AsyncMock)
        assert smtp.login.called
        assert smtp.send_message.called
