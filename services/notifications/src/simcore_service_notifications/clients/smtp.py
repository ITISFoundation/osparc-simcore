from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aiosmtplib import SMTP

from ..models.smtp import EmailProtocol, SMTPSettings


@asynccontextmanager
async def create_session(
    settings: SMTPSettings,
) -> AsyncIterator[SMTP]:
    async with SMTP(
        hostname=settings.host,
        port=settings.port,
        # FROM https://aiosmtplib.readthedocs.io/en/stable/usage.html#starttls-connections
        # By default, if the server advertises STARTTLS support, aiosmtplib will upgrade the connection automatically.
        # Setting use_tls=True for STARTTLS servers will typically result in a connection error
        # To opt out of STARTTLS on connect, pass start_tls=False.
        # NOTE: for that reason TLS and STARTTLS are mutually exclusive
        use_tls=settings.protocol == EmailProtocol.TLS,
        start_tls=settings.protocol == EmailProtocol.STARTTLS,
    ) as smtp:
        if settings.has_credentials:
            assert settings.username  # nosec
            assert settings.password  # nosec
            await smtp.login(
                settings.username,
                settings.password.get_secret_value(),
            )

        yield smtp
