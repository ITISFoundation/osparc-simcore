import logging
import mimetypes
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from os.path import join
from pathlib import Path
from pprint import pformat
from typing import Any, Mapping, NamedTuple, Optional, Union

import aiosmtplib
from aiohttp import web
from aiohttp_jinja2 import render_string
from settings_library.email import EmailProtocol
from simcore_service_webserver.products import get_product_template_path

from .._resources import resources
from .settings import LoginOptions, get_plugin_options

log = logging.getLogger(__name__)


async def _send_mail(*, message: Union[MIMEText, MIMEMultipart], cfg: LoginOptions):
    log.debug("Email configuration %s", cfg)
    smtp_args = dict(
        hostname=cfg.SMTP_HOST,
        port=cfg.SMTP_PORT,
        use_tls=cfg.SMTP_PROTOCOL == EmailProtocol.TLS,
        start_tls=cfg.SMTP_PROTOCOL == EmailProtocol.STARTTLS,
    )
    log.debug("Sending email with smtp configuration: %s", pformat(smtp_args))
    if cfg.SMTP_PORT == 587:
        # NOTE: aiosmtplib does not handle port 587 correctly
        # this is a workaround
        smtp = aiosmtplib.SMTP(**smtp_args)
        if cfg.SMTP_PROTOCOL == EmailProtocol.STARTTLS:
            log.info("Unencrypted connection attempt to mailserver ...")
            await smtp.connect(use_tls=False, port=cfg.SMTP_PORT)
            log.info("Starting STARTTLS ...")
            await smtp.starttls()
        elif cfg.SMTP_PROTOCOL == EmailProtocol.TLS:
            await smtp.connect(use_tls=True, port=cfg.SMTP_PORT)
        elif cfg.SMTP_PROTOCOL == EmailProtocol.UNENCRYPTED:
            await smtp.connect(use_tls=False, port=cfg.SMTP_PORT)
            log.info("Unencrypted connection attempt to mailserver ...")
        #
        if cfg.SMTP_USERNAME and cfg.SMTP_PASSWORD:
            log.info("Attempting a login into the email server ...")
            await smtp.login(cfg.SMTP_USERNAME, cfg.SMTP_PASSWORD.get_secret_value())
        await smtp.send_message(message)
        await smtp.quit()
    else:
        async with aiosmtplib.SMTP(**smtp_args) as smtp:
            if cfg.SMTP_USERNAME and cfg.SMTP_PASSWORD:
                log.info("Login email server ...")
                await smtp.login(
                    cfg.SMTP_USERNAME, cfg.SMTP_PASSWORD.get_secret_value()
                )
            await smtp.send_message(message)


async def _compose_mail(
    *,
    cfg: LoginOptions,
    sender: str,
    recipient: str,
    subject: str,
    body: str,
) -> None:
    msg = MIMEText(body, "html")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient

    await _send_mail(cfg=cfg, message=msg)


class AttachmentTuple(NamedTuple):
    filename: str
    payload: bytearray


async def _compose_multipart_mail(
    *,
    cfg: LoginOptions,
    sender: str,
    recipient: str,
    subject: str,
    body: str,
    attachments: list[AttachmentTuple],
) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient

    part1 = MIMEText(body, "html")
    msg.attach(part1)

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
        msg.attach(part)

    await _send_mail(cfg=cfg, message=msg)


def themed(dirname, template) -> Path:
    return resources.get_path(join(dirname, template))


async def get_template_path(request: web.Request, filename: str) -> Path:
    return await get_product_template_path(request, filename)


async def render_and_send_mail(
    request: web.Request,
    *,
    from_: str,
    to: str,
    template: Path,
    context: Mapping[str, Any],
    attachments: Optional[list[AttachmentTuple]] = None,
):
    page = render_string(template_name=f"{template}", request=request, context=context)
    #
    # NOTE: By CONVENTION, it expects first line of the template
    # to be the Subject of the email.
    #
    subject, body = page.split("\n", 1)

    cfg: LoginOptions = get_plugin_options(request.app)
    if attachments:
        await _compose_multipart_mail(
            cfg=cfg,
            sender=from_,
            recipient=to,
            subject=subject.strip(),
            body=body,
            attachments=attachments,
        )
    else:
        await _compose_mail(
            cfg=cfg,
            sender=from_,
            recipient=to,
            subject=subject.strip(),
            body=body,
        )
