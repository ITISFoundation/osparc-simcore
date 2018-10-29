import random
import string
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from logging import getLogger
from os.path import join

import aiosmtplib
import passlib.hash
from aiohttp.web import HTTPFound
from aiohttp_jinja2 import render_string

from ..resources import resources
from .cfg import cfg

CHARS = string.ascii_uppercase + string.ascii_lowercase + string.digits
log = getLogger(__name__)


def encrypt_password(password):
    return passlib.hash.sha256_crypt.encrypt(password, rounds=1000)


def check_password(password, password_hash):
    return passlib.hash.sha256_crypt.verify(password, password_hash)


def get_random_string(min_len, max_len=None):
    max_len = max_len or min_len
    size = random.randint(min_len, max_len)
    return ''.join(random.choice(CHARS) for x in range(size))


async def make_confirmation_link(request, confirmation):
    link = url_for('auth_confirmation', code=confirmation['code'])
    return '{}://{}{}'.format(request.scheme, request.host, link)


async def is_confirmation_allowed(user, action):
    db = cfg.STORAGE
    confirmation = await db.get_confirmation({'user': user, 'action': action})
    if not confirmation:
        return True
    if is_confirmation_expired(confirmation):
        await db.delete_confirmation(confirmation)
        return True


def is_confirmation_expired(confirmation):
    age = datetime.utcnow() - confirmation['created_at']
    lifetime_days = cfg['{}_CONFIRMATION_LIFETIME'.format(
        confirmation['action'].upper())]
    lifetime = timedelta(days=lifetime_days)
    return age > lifetime


def url_for(urlname, *args, **kwargs):
    if str(urlname).startswith(('/', 'http://', 'https://')):
        return urlname
    return cfg.APP.router[urlname].url_for(*args, **kwargs)


def redirect(urlname, *args, **kwargs):
    return HTTPFound(url_for(urlname, *args, **kwargs))


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
        use_tls=cfg.SMTP_TLS,
    )
    msg = MIMEText(body, 'html')
    msg['Subject'] = subject
    msg['From'] = cfg.SMTP_SENDER
    msg['To'] = recipient

    if cfg.SMTP_PORT == 587:
        # aiosmtplib does not handle port 587 correctly
        # plaintext first, then use starttls
        # this is a workaround
        smtp = aiosmtplib.SMTP(**smtp_args)
        await smtp.connect(use_tls=False, port=cfg.SMTP_PORT)
        if cfg.SMTP_TLS:
            await smtp.starttls(validate_certs=False)
        if cfg.SMTP_USERNAME:
            await smtp.login(cfg.SMTP_USERNAME, cfg.SMTP_PASSWORD)
        await smtp.send_message(msg)
        await smtp.quit()
    else:
        async with aiosmtplib.SMTP(**smtp_args) as smtp:
            if cfg.SMTP_USERNAME:
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
