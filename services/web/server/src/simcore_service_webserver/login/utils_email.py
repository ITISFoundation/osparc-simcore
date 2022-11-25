import logging
import mimetypes
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from os.path import join
from pathlib import Path
from pprint import pformat
from typing import Any, Mapping, Optional, Union

import aiosmtplib
from aiohttp import web
from aiohttp_jinja2 import render_string
from settings_library.email import EmailProtocol
from simcore_service_webserver.products import get_product_template_path

from .._resources import resources
from .settings import LoginOptions, get_plugin_options

log = logging.getLogger(__name__)


async def _send_mail(app: web.Application, msg: Union[MIMEText, MIMEMultipart]):
    cfg: LoginOptions = get_plugin_options(app)
    log.debug("Email configuration %s", cfg)

    msg["From"] = cfg.SMTP_SENDER
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
        await smtp.send_message(msg)
        await smtp.quit()
    else:
        async with aiosmtplib.SMTP(**smtp_args) as smtp:
            if cfg.SMTP_USERNAME and cfg.SMTP_PASSWORD:
                log.info("Login email server ...")
                await smtp.login(
                    cfg.SMTP_USERNAME, cfg.SMTP_PASSWORD.get_secret_value()
                )
            await smtp.send_message(msg)


async def _compose_mail(
    app: web.Application, recipient: str, subject: str, body: str
) -> None:
    msg = MIMEText(body, "html")
    msg["Subject"] = subject
    msg["To"] = recipient

    await _send_mail(app, msg)


async def _compose_multipart_mail(
    app: web.Application,
    recipient: str,
    subject: str,
    body: str,
    attachments: list[tuple[str, bytearray]],
) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["To"] = recipient

    part1 = MIMEText(body, "html")
    msg.attach(part1)

    for attachment in attachments:
        filename = attachment[0]
        payload = attachment[1]
        mimetype = mimetypes.guess_type(filename)[0].split("/")
        part = MIMEBase(mimetype[0], mimetype[1])
        part.set_payload(payload)
        part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
        encoders.encode_base64(part)
        msg.attach(part)

    await _send_mail(app, msg)


def themed(dirname, template) -> Path:
    return resources.get_path(join(dirname, template))


async def get_template_path(request: web.Request, filename: str) -> Path:
    return await get_product_template_path(request, filename)


async def render_and_send_mail(
    request: web.Request,
    to: str,
    template: Path,
    context: Mapping[str, Any],
    attachments: Optional[list[tuple[str, bytearray]]] = None,
):
    page = render_string(template_name=f"{template}", request=request, context=context)
    # NOTE: Expects first line of the template to be the Subject of the email
    subject, body = page.split("\n", 1)

    if attachments:
        await _compose_multipart_mail(
            request.app, to, subject.strip(), body, attachments
        )
    else:
        await _compose_mail(request.app, to, subject.strip(), body)
