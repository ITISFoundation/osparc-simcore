import mimetypes
import random
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from logging import getLogger
from os.path import join
from pprint import pformat
from typing import List, Mapping, Optional, Tuple

import aiosmtplib
import attr
import passlib.hash
from aiohttp import web
from aiohttp_jinja2 import render_string
from passlib import pwd
from servicelib.aiohttp.rest_models import LogMessageType
from servicelib.json_serialization import json_dumps

from ..resources import resources
from .cfg import cfg  # TODO: remove this singleton!!!

log = getLogger(__name__)


def encrypt_password(password: str) -> str:
    # TODO: add settings sha256_crypt.using(**settings).hash(secret)
    # see https://passlib.readthedocs.io/en/stable/lib/passlib.hash.sha256_crypt.html
    #
    return passlib.hash.sha256_crypt.using(rounds=1000).hash(password)


def check_password(password: str, password_hash: str) -> bool:
    return passlib.hash.sha256_crypt.verify(password, password_hash)


def get_random_string(min_len: int, max_len: Optional[int] = None) -> str:
    max_len = max_len or min_len
    size = random.randint(min_len, max_len)
    return pwd.genword(entropy=52, length=size)


def get_client_ip(request: web.Request) -> str:
    try:
        ips = request.headers["X-Forwarded-For"]
    except KeyError:
        ips = request.transport.get_extra_info("peername")[0]
    return ips.split(",")[0]


async def compose_mail(recipient: str, subject: str, body: str) -> None:
    msg = MIMEText(body, "html")
    msg["Subject"] = subject
    msg["From"] = cfg.SMTP_SENDER
    msg["To"] = recipient

    await send_mail(msg)


async def compose_multipart_mail(
    recipient: str, subject: str, body: str, attachments: List[Tuple[str, bytearray]]
) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg.SMTP_SENDER
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

    await send_mail(msg)


async def render_and_send_mail(
    request: web.Request,
    to: str,
    template: str,
    context: Mapping,
    attachments: Optional[List[Tuple[str, bytearray]]] = None,
):
    page = render_string(str(template), request, context)
    subject, body = page.split("\n", 1)
    if attachments:
        await compose_multipart_mail(to, subject.strip(), body, attachments)
    else:
        await compose_mail(to, subject.strip(), body)


def themed(template):
    return resources.get_path(join(cfg.THEME, template))


def common_themed(template):
    return resources.get_path(join(cfg.COMMON_THEME, template))


def flash_response(msg: str, level: str = "INFO") -> web.Response:
    response = web.json_response(
        data={"data": attr.asdict(LogMessageType(msg, level)), "error": None},
        dumps=json_dumps,
    )
    return response


async def send_mail(msg):
    smtp_args = dict(
        loop=cfg.APP.loop,
        hostname=cfg.SMTP_HOST,
        port=cfg.SMTP_PORT,
        use_tls=bool(cfg.SMTP_TLS_ENABLED),
    )
    log.debug("Sending email with smtp configuration: %s", pformat(smtp_args))
    if cfg.SMTP_PORT == 587:
        # NOTE: aiosmtplib does not handle port 587 correctly
        # plaintext first, then use starttls
        # this is a workaround
        smtp = aiosmtplib.SMTP(**smtp_args)
        await smtp.connect(use_tls=False, port=cfg.SMTP_PORT)
        if cfg.SMTP_TLS_ENABLED:
            log.info("Starting TLS ...")
            await smtp.starttls(validate_certs=False)
        if cfg.SMTP_USERNAME:
            log.info("Login email server ...")
            await smtp.login(cfg.SMTP_USERNAME, cfg.SMTP_PASSWORD)
        await smtp.send_message(msg)
        await smtp.quit()
    else:
        async with aiosmtplib.SMTP(**smtp_args) as smtp:
            if cfg.SMTP_USERNAME:
                log.info("Login email server ...")
                await smtp.login(cfg.SMTP_USERNAME, cfg.SMTP_PASSWORD)
            await smtp.send_message(msg)
