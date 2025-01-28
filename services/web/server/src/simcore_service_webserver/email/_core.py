import logging
import mimetypes
import re
from collections.abc import Mapping
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from pathlib import Path
from typing import Any, NamedTuple, TypedDict, Union

import aiosmtplib
from aiohttp import web
from aiohttp_jinja2 import render_string
from settings_library.email import EmailProtocol, SMTPSettings

from .settings import get_plugin_settings

_logger = logging.getLogger(__name__)


def _create_smtp_client(settings: SMTPSettings) -> aiosmtplib.SMTP:
    return aiosmtplib.SMTP(
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        use_tls=settings.SMTP_PROTOCOL == EmailProtocol.TLS,
        start_tls=settings.SMTP_PROTOCOL == EmailProtocol.STARTTLS,
    )


async def _do_send_mail(
    *, message: MIMEText | MIMEMultipart, settings: SMTPSettings
) -> None:
    """
    WARNING: _do_send_mail is mocked so be careful when changing the signature or name !!
    """

    _logger.debug("Email configuration %s", settings.model_dump_json(indent=1))

    if settings.SMTP_PORT == 587:
        # NOTE: aiosmtplib does not handle port 587 correctly this is a workaround
        try:
            smtp_on_587_port = _create_smtp_client(settings)

            if settings.SMTP_PROTOCOL == EmailProtocol.STARTTLS:
                _logger.info("Unencrypted connection attempt to mailserver ...")
                await smtp_on_587_port.connect(use_tls=False, port=settings.SMTP_PORT)
                _logger.info("Starting STARTTLS ...")
                await smtp_on_587_port.starttls()

            elif settings.SMTP_PROTOCOL == EmailProtocol.TLS:
                await smtp_on_587_port.connect(use_tls=True, port=settings.SMTP_PORT)

            elif settings.SMTP_PROTOCOL == EmailProtocol.UNENCRYPTED:
                _logger.info("Unencrypted connection attempt to mailserver ...")
                await smtp_on_587_port.connect(use_tls=False, port=settings.SMTP_PORT)

            if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                _logger.info("Attempting a login into the email server ...")
                await smtp_on_587_port.login(
                    settings.SMTP_USERNAME, settings.SMTP_PASSWORD.get_secret_value()
                )

            await smtp_on_587_port.send_message(message)
        finally:
            await smtp_on_587_port.quit()
    else:
        smtp_client = _create_smtp_client(settings)
        async with smtp_client:
            if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                _logger.info("Login email server ...")
                await smtp_client.login(
                    settings.SMTP_USERNAME, settings.SMTP_PASSWORD.get_secret_value()
                )
            await smtp_client.send_message(message)


MIMEMessage = Union[MIMEText, MIMEMultipart]


def _compose_mime(
    message: MIMEMessage,
    settings: SMTPSettings,
    *,
    sender: str,
    recipient: str,
    subject: str,
    reply_to: str | None = None,
) -> None:
    # SEE required fields https://www.rfc-editor.org/rfc/rfc5322#section-3.6
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message["Date"] = formatdate()
    message["Message-ID"] = make_msgid(domain=settings.SMTP_HOST)
    if reply_to:
        message["Reply-To"] = reply_to


class SMTPServerInfo(TypedDict):
    hostname: str
    port: int
    timeout: float
    use_tls: bool


async def check_email_server_responsiveness(settings: SMTPSettings) -> SMTPServerInfo:
    """Raises SMTPException if cannot connect otherwise settings"""
    async with _create_smtp_client(settings) as smtp:
        assert smtp.hostname  # nosec
        assert smtp.port  # nosec
        assert smtp.timeout  # nosec
        return SMTPServerInfo(
            hostname=smtp.hostname,
            port=smtp.port,
            timeout=smtp.timeout,
            use_tls=smtp.use_tls,
        )


async def _send_email(
    *,
    settings: SMTPSettings,
    sender: str,
    recipient: str,
    subject: str,
    body: str,
    reply_to: str | None = None,
) -> MIMEMessage:
    """
    Sends an email with a body/subject marked as html
    """
    message = MIMEText(body, "html")
    _compose_mime(
        message,
        settings=settings,
        sender=sender,
        recipient=recipient,
        subject=subject,
        reply_to=reply_to,
    )
    await _do_send_mail(settings=settings, message=message)
    return message


class AttachmentTuple(NamedTuple):
    filename: str
    payload: bytearray


async def _send_email_with_attachements(
    *,
    settings: SMTPSettings,
    sender: str,
    recipient: str,
    subject: str,
    body: str,
    attachments: list[AttachmentTuple],
    reply_to: str | None = None,
) -> MIMEMessage:
    """
    Sends an email with a body/subject marked as html with file attachement/s
    """
    # NOTE: Intentionally separated from send_email to further optimize legacy code

    message = MIMEMultipart()
    _compose_mime(
        message,
        settings=settings,
        sender=sender,
        recipient=recipient,
        subject=subject,
        reply_to=reply_to,
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
    return message


def _remove_comments(html_string: str) -> str:
    # WARNING: this function is patched somewhere in the tests. Be aware that if you change
    # the signature the mock.patch will fail!
    return re.sub(r"<!--.*?-->", "", html_string, flags=re.DOTALL)


def _render_template(
    request: web.Request,
    template: Path,
    context: Mapping[str, Any],
) -> tuple[str, str]:
    page = render_string(template_name=f"{template}", request=request, context=context)
    #
    # NOTE: By CONVENTION, it expects first line of the template
    # to be the Subject of the email.
    #
    subject, body = page.split("\n", 1)

    # formats body (avoids spam)
    subject = subject.strip()
    body = _remove_comments(body).strip()

    if "<html>" not in body:
        html_body = f"<!DOCTYPE html><html><head></head><body>\n{body}\n</body></html>"
    else:
        html_body = body

    return subject, html_body


async def send_email_from_template(
    request: web.Request,
    *,
    from_: str,
    to: str,
    template: Path,
    context: Mapping[str, Any],
    attachments: list[AttachmentTuple] | None = None,
    reply_to: str | None = None,
):
    """Render template in context and send email w/ or w/o attachments"""
    settings: SMTPSettings = get_plugin_settings(request.app)
    subject, body = _render_template(request, template, context)

    if attachments:
        return await _send_email_with_attachements(
            settings=settings,
            sender=from_,
            recipient=to,
            subject=subject,
            body=body,
            attachments=attachments,
            reply_to=reply_to,
        )

    return await _send_email(
        settings=settings,
        sender=from_,
        recipient=to,
        subject=subject,
        body=body,
        reply_to=reply_to,
    )
