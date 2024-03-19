import logging
import mimetypes
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from email.headerregistry import Address
from email.message import EmailMessage
from pathlib import Path
from typing import cast

from aiosmtplib import SMTP
from settings_library.email import EmailProtocol, SMTPSettings

_logger = logging.getLogger(__name__)


def compose_email(
    from_: Address,
    to: Address,
    subject: str,
    content_text: str,
    content_html: str | None = None,
    reply_to: Address | None = None,
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = from_
    msg["To"] = to
    if reply_to:
        msg["Reply-To"] = reply_to

    msg["Subject"] = subject

    msg.set_content(content_text)
    if content_html:
        msg.add_alternative(content_html, subtype="html")
    return msg


def _guess_file_type(file_path: Path) -> tuple[str, str]:
    assert file_path.is_file()
    mimetype, _encoding = mimetypes.guess_type(file_path)
    if mimetype:
        maintype, subtype = mimetype.split("/", maxsplit=1)
    else:
        maintype, subtype = "application", "octet-stream"
    return maintype, subtype


def add_attachments(msg: EmailMessage, file_paths: list[Path]):
    for attachment_path in file_paths:
        maintype, subtype = _guess_file_type(attachment_path)
        msg.add_attachment(
            attachment_path.read_bytes(),
            filename=attachment_path.name,
            maintype=maintype,
            subtype=subtype,
        )


@asynccontextmanager
async def create_email_session(
    settings: SMTPSettings,
) -> AsyncIterator[SMTP]:
    async with SMTP(
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
            assert settings.SMTP_USERNAME  # nosec
            assert settings.SMTP_PASSWORD  # nosec
            await smtp.login(
                settings.SMTP_USERNAME,
                settings.SMTP_PASSWORD.get_secret_value(),
            )

        yield cast(SMTP, smtp)
