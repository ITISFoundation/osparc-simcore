# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from faker import Faker
from models_library.products import ProductName
from notifications_library._email import (
    add_attachments,
    compose_email,
    create_email_session,
)
from notifications_library._render import (
    ProductData,
    UserData,
    create_default_env,
    render_email_parts,
)
from notifications_library.payments import PaymentData
from pydantic import EmailStr
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from settings_library.email import SMTPSettings


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


@pytest.fixture
def smtp_mock_or_none(
    mocker: MockerFixture, external_user_email: EmailStr | None
) -> MagicMock | None:
    if not external_user_email:
        return mocker.patch("notifications_library._email.SMTP")
    print("🚨 Emails might be sent to", external_user_email)
    return None


async def test_send_email_workflow(
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
    """
    Example of usage with external email and envfile

        > pytest --external-user-email=me@email.me --external-envfile=.myenv -k test_send_email_workflow  --pdb tests/unit
    """

    settings = SMTPSettings.create_from_envs()
    env = create_default_env()

    assert user_data.email == user_email
    assert product_data == product_name

    parts = render_email_parts(
        env,
        event_name="on_payed",
        user=user_data,
        product=product_data,
        extra={"payment": payment_data},
    )

    assert parts.from_.addr_spec == user_email
    assert parts.to.addr_spec == product_data.support_email

    msg = compose_email(*parts)

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
