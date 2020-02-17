import random
import string
from email.mime.text import MIMEText
from logging import getLogger
from os.path import join
from pprint import pformat

import aiosmtplib
import attr
import passlib.hash
from aiohttp_jinja2 import render_string

from aiohttp import web
from servicelib.rest_models import LogMessageType

from ..resources import resources
from .cfg import cfg  # TODO: remove this singleton!!!

CHARS = string.ascii_uppercase + string.ascii_lowercase + string.digits
log = getLogger(__name__)


def encrypt_password(password):
    #TODO: add settings sha256_crypt.using(**settings).hash(secret)
    # see https://passlib.readthedocs.io/en/stable/lib/passlib.hash.sha256_crypt.html
    #
    return passlib.hash.sha256_crypt.using(rounds=1000).hash(password)


def check_password(password, password_hash):
    return passlib.hash.sha256_crypt.verify(password, password_hash)


def get_random_string(min_len, max_len=None):
    max_len = max_len or min_len
    size = random.randint(min_len, max_len)
    return ''.join(random.choice(CHARS) for x in range(size))


def get_client_ip(request):
    try:
        ips = request.headers['X-Forwarded-For']
    except KeyError:
        ips = request.transport.get_extra_info('peername')[0]
    return ips.split(',')[0]


async def send_mail(recipient, subject, body):
    # TODO: move to email submodule
    smtp_args = dict(
        loop=cfg.APP.loop,
        hostname=cfg.SMTP_HOST,
        port=cfg.SMTP_PORT,
        use_tls=bool(cfg.SMTP_TLS_ENABLED),
    )
    log.debug("Sending email with smtp configuration: %s", pformat(smtp_args))

    msg = MIMEText(body, 'html')
    msg['Subject'] = subject
    msg['From'] = cfg.SMTP_SENDER
    msg['To'] = recipient

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

async def render_and_send_mail(request, to, template, context=None):
    page = render_string(str(template), request, context)
    subject, body = page.split('\n', 1)
    await send_mail(to, subject.strip(), body)


def themed(template):
    return resources.get_path(join(cfg.THEME, template))

def common_themed(template):
    return resources.get_path(join(cfg.COMMON_THEME, template))

def flash_response(msg: str, level: str="INFO"):
    response = web.json_response(data={
        'data': attr.asdict(LogMessageType(msg, level)),
        'error': None
    })
    return response
