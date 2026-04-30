from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aiosmtplib import SMTP
from settings_library.email import EmailProtocol, SMTPSettings


@asynccontextmanager
async def create_session(
    settings: SMTPSettings,
) -> AsyncIterator[SMTP]:
    async with SMTP(
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        # FROM https://aiosmtplib.readthedocs.io/en/stable/usage.html#starttls-connections
        # By default, if the server advertises STARTTLS support, aiosmtplib will upgrade the connection automatically.
        # Setting use_tls=True for STARTTLS servers will typically result in a connection error
        # To opt out of STARTTLS on connect, pass start_tls=False.
        # NOTE: for that reason TLS and STARTTLS are mutually exclusive
        use_tls=settings.SMTP_PROTOCOL == EmailProtocol.TLS,
        start_tls=settings.SMTP_PROTOCOL == EmailProtocol.STARTTLS,
    ) as smtp:
        if settings.has_credentials:
            assert settings.SMTP_USERNAME  # nosec
            assert settings.SMTP_PASSWORD  # nosec
            await smtp.login(
                settings.SMTP_USERNAME,
                settings.SMTP_PASSWORD.get_secret_value(),
            )

        yield smtp
