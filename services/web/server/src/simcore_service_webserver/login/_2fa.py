""" two-factor-authentication utils

Currently includes two parts:

- generation and storage of secret codes for 2FA validation (using redis)
- sending SMS of generated codes for validation (using twilio service)

"""

import asyncio
import logging
import secrets
from typing import Optional

from aiohttp import web
from pydantic import BaseModel, Field
from servicelib.logging_utils import log_decorator
from settings_library.twilio import TwilioSettings
from twilio.rest import Client

from ..redis import get_redis_validation_code_client
from .utils_email import get_template_path, render_and_send_mail

log = logging.getLogger(__name__)


class ValidationCode(BaseModel):
    value: str = Field(..., description="The code")


#
# REDIS:
#  is used for generation and storage of secret codes
#
# SEE https://redis-py.readthedocs.io/en/stable/index.html


def _generage_2fa_code() -> str:
    return f"{1000 + secrets.randbelow(8999)}"  # code between [1000, 9999)


@log_decorator(log, level=logging.DEBUG)
async def create_2fa_code(
    app: web.Application,
    user_email: str,
    *,
    expiration_time: int = 60,
) -> str:
    """Saves 2FA code with an expiration time, i.e. a finite Time-To-Live (TTL)"""
    redis_client = get_redis_validation_code_client(app)
    hash_key, code = user_email, _generage_2fa_code()
    await redis_client.set(hash_key, value=code, ex=expiration_time)
    return code


@log_decorator(log, level=logging.DEBUG)
async def get_2fa_code(app: web.Application, user_email: str) -> Optional[str]:
    """Returns 2FA code for user or None if it does not exist (e.g. expired or never set)"""
    redis_client = get_redis_validation_code_client(app)
    hash_key = user_email
    return await redis_client.get(hash_key)


@log_decorator(log, level=logging.DEBUG)
async def delete_2fa_code(app: web.Application, user_email: str) -> None:
    redis_client = get_redis_validation_code_client(app)
    hash_key = user_email
    await redis_client.delete(hash_key)


#
# TWILIO
#   - sms service
#


@log_decorator(log, level=logging.DEBUG)
async def send_sms_code(
    phone_number: str,
    code: str,
    twilo_auth: TwilioSettings,
    twilio_messaging_sid: str,
    twilio_alpha_numeric_sender: str,
    user_name: str = "user",
):
    create_kwargs = {
        "messaging_service_sid": twilio_messaging_sid,
        "to": phone_number,
        "body": f"Dear {user_name[:20].capitalize().strip()}, your verification code is {code}",
    }
    if twilo_auth.is_alphanumeric_supported(phone_number):
        create_kwargs["from_"] = twilio_alpha_numeric_sender

    def _sender():
        log.info(
            "Sending sms code to %s from product %s",
            f"{phone_number=}",
            twilio_alpha_numeric_sender,
        )
        #
        # SEE https://www.twilio.com/docs/sms/quickstart/python
        #
        client = Client(twilo_auth.TWILIO_ACCOUNT_SID, twilo_auth.TWILIO_AUTH_TOKEN)
        message = client.messages.create(**create_kwargs)

        log.debug(
            "Got twilio client %s",
            f"{message=}",
        )

    await asyncio.get_event_loop().run_in_executor(None, _sender)


#
# EMAIL
#


@log_decorator(log, level=logging.DEBUG)
async def send_email_code(
    request: web.Request,
    user_email: str,
    support_email: str,
    code: str,
    user_name: str = "user",
):
    email_template_path = await get_template_path(request, "new_2fa_code.jinja2")
    await render_and_send_mail(
        request,
        from_=support_email,
        to=user_email,
        template=email_template_path,
        context={
            "host": request.host,
            "code": code,
            "name": user_name.capitalize(),
            "support_email": support_email,
        },
    )


#
# HELPERS
#

_FROM, _TO = 3, -1


def mask_phone_number(phn: str) -> str:
    assert len(phn) > 5  # nosec
    # SEE https://github.com/pydantic/pydantic/issues/1551
    # SEE https://en.wikipedia.org/wiki/E.164
    return phn[:_FROM] + len(phn[_FROM:_TO]) * "X" + phn[_TO:]
