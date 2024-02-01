# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import aiosmtplib
import pytest
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_envfile
from settings_library.email import EmailProtocol, SMTPSettings


@pytest.fixture
def tmp_environment(
    osparc_simcore_root_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    return setenvs_from_envfile(monkeypatch, osparc_simcore_root_dir / ".secrets")


async def test_it(tmp_environment: EnvVarsDict):

    settings = SMTPSettings.create_from_envs()

    async with aiosmtplib.SMTP(
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        # FROM https://aiosmtplib.readthedocs.io/en/stable/usage.html#starttls-connections
        # By default, if the server advertises STARTTLS support, aiosmtplib will upgrade the connection automatically.
        # Setting use_tls=True for STARTTLS servers will typically result in a connection error
        # To opt out of STARTTLS on connect, pass start_tls=False.
        # NOTE: for that reason TLS and STARTLS are mutally exclusive
        use_tls=settings.SMTP_PROTOCOL == EmailProtocol.TLS,
        start_tls=settings.SMTP_PROTOCOL == EmailProtocol.STARTTLS,
    ) as smtp:
        if settings.has_credentials:
            assert settings.SMTP_USERNAME
            assert settings.SMTP_PASSWORD
            await smtp.login(
                settings.SMTP_USERNAME,
                settings.SMTP_PASSWORD.get_secret_value(),
            )

        # Session ready to send email

        def compose_simple():
            # compose simple
            msg = EmailMessage()
            msg["From"] = "support@osparc.io"
            msg["To"] = "crespo@speag.com"
            msg["Subject"] = "Hello World!"
            msg.set_content("Sent via aiosmtplib")
            return msg

        def compose_multipart():
            # multipart
            msg = MIMEMultipart("alternative")
            msg["From"] = "support@osparc.io"
            msg["To"] = "crespo@speag.com"
            msg["Subject"] = "Hello World!"

            plain_text_message = MIMEText("Sent via aiosmtplib", "plain", "utf-8")
            html_message = MIMEText(
                "<html><body><h1>Sent via aiosmtplib</h1></body></html>",
                "html",
                "utf-8",
            )
            msg.attach(plain_text_message)
            msg.attach(html_message)
            return msg

        await smtp.send_message(compose_simple())
        await smtp.send_message(compose_multipart())
