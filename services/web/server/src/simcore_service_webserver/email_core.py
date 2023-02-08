import logging
import mimetypes
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from pathlib import Path
from pprint import pformat
from typing import Any, Mapping, NamedTuple, Optional, TypedDict, Union

import aiosmtplib
from aiohttp import web
from aiohttp_jinja2 import render_string
from settings_library.email import EmailProtocol, SMTPSettings

from .email_settings import get_plugin_settings

logger = logging.getLogger(__name__)


def _create_smtp_client(settings: SMTPSettings) -> aiosmtplib.SMTP:
    smtp_args = dict(
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        use_tls=settings.SMTP_PROTOCOL == EmailProtocol.TLS,
        start_tls=settings.SMTP_PROTOCOL == EmailProtocol.STARTTLS,
    )
    logger.debug("Sending email with smtp configuration: %s", pformat(smtp_args))
    return aiosmtplib.SMTP(**smtp_args)


async def _do_send_mail(
    *, message: Union[MIMEText, MIMEMultipart], settings: SMTPSettings
) -> None:
    # WARNING: _do_send_mail is mocked so be careful when changing the signature or name !!

    logger.debug("Email configuration %s", settings.json(indent=1))
    logger.debug("%s", f"{message=}")

    if settings.SMTP_PORT == 587:
        # NOTE: aiosmtplib does not handle port 587 correctly this is a workaround
        try:
            smtp = _create_smtp_client(settings)

            if settings.SMTP_PROTOCOL == EmailProtocol.STARTTLS:
                logger.info("Unencrypted connection attempt to mailserver ...")
                await smtp.connect(use_tls=False, port=settings.SMTP_PORT)
                logger.info("Starting STARTTLS ...")
                await smtp.starttls()

            elif settings.SMTP_PROTOCOL == EmailProtocol.TLS:
                await smtp.connect(use_tls=True, port=settings.SMTP_PORT)

            elif settings.SMTP_PROTOCOL == EmailProtocol.UNENCRYPTED:
                logger.info("Unencrypted connection attempt to mailserver ...")
                await smtp.connect(use_tls=False, port=settings.SMTP_PORT)

            if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                logger.info("Attempting a login into the email server ...")
                await smtp.login(
                    settings.SMTP_USERNAME, settings.SMTP_PASSWORD.get_secret_value()
                )

            await smtp.send_message(message)
        finally:
            await smtp.quit()
    else:
        async with _create_smtp_client(settings) as smtp:
            if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                logger.info("Login email server ...")
                await smtp.login(
                    settings.SMTP_USERNAME, settings.SMTP_PASSWORD.get_secret_value()
                )
            await smtp.send_message(message)


def _compose_mime(
    message: Union[MIMEText, MIMEMultipart],
    *,
    sender: str,
    recipient: str,
    subject: str,
) -> None:
    # SEE required fields https://www.rfc-editor.org/rfc/rfc5322#section-3.6
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message["Date"] = formatdate()
    message["Message-ID"] = make_msgid()


class SMTPServerInfo(TypedDict):
    hostname: str
    port: int
    timeout: float
    use_tls: bool


async def check_email_server_responsiveness(settings: SMTPSettings) -> SMTPServerInfo:
    """Raises SMTPException if cannot connect otherwise settings"""
    async with _create_smtp_client(settings) as smtp:
        return SMTPServerInfo(
            hostname=smtp.hostname,
            port=smtp.port,
            timeout=smtp.timeout,
            user_tls=smtp.use_tls,
        )


async def send_email(
    *,
    settings: SMTPSettings,
    sender: str,
    recipient: str,
    subject: str,
    body: str,
) -> None:
    """
    Sends an email with a body/subject marked as html
    """
    message = MIMEText(body, "html")
    _compose_mime(
        message,
        sender=sender,
        recipient=recipient,
        subject=subject,
    )
    await _do_send_mail(settings=settings, message=message)


class AttachmentTuple(NamedTuple):
    filename: str
    payload: bytearray


async def send_email_with_attachements(
    *,
    settings: SMTPSettings,
    sender: str,
    recipient: str,
    subject: str,
    body: str,
    attachments: list[AttachmentTuple],
) -> None:
    """
    Sends an email with a body/subject marked as html with file attachement/s
    """
    # NOTE: Intentionally separated from send_email to further optimize legacy code

    message = MIMEMultipart()
    _compose_mime(
        message,
        sender=sender,
        recipient=recipient,
        subject=subject,
    )
    message.attach(MIMEText(body, "html"))

    for attachment in attachments:
        mimetype, _encoding = mimetypes.guess_type(attachment.filename)
        if not mimetype:
            # default if guess fails
            main_type, subtype = "application", "octet-stream"
        else:
            main_type, subtype = mimetype.split("/", maxsplit=1)

        part = MIMEBase(main_type, subtype)
        part.set_payload(attachment.payload)
        part.add_header(
            "Content-Disposition", f'attachment; filename="{attachment.filename}"'
        )
        encoders.encode_base64(part)
        message.attach(part)

    await _do_send_mail(settings=settings, message=message)


def _render_template(
    request: web.Request,
    template: Path,
    context: Mapping[str, Any],
):
    page = render_string(template_name=f"{template}", request=request, context=context)
    #
    # NOTE: By CONVENTION, it expects first line of the template
    # to be the Subject of the email.
    #
    subject, body = page.split("\n", 1)
    return subject.strip(), body


async def send_email_from_template(
    request: web.Request,
    *,
    from_: str,
    to: str,
    template: Path,
    context: Mapping[str, Any],
    attachments: Optional[list[AttachmentTuple]] = None,
):
    """Render template in context and send email w/ or w/o attachments"""
    settings: SMTPSettings = get_plugin_settings(request.app)
    subject, body = _render_template(request, template, context)

    if attachments:
        await send_email_with_attachements(
            settings=settings,
            sender=from_,
            recipient=to,
            subject=subject,
            body=body,
            attachments=attachments,
        )
    else:
        await send_email(
            settings=settings,
            sender=from_,
            recipient=to,
            subject=subject,
            body=body,
        )
