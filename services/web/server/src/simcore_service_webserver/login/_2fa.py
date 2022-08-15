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
from twilio.rest import Client

from ..redis import get_redis_validation_code_client
from .settings import TwilioSettings

log = logging.getLogger(__name__)


class ValidationCode(BaseModel):
    value: str = Field(..., description="The code")


#
# REDIS:
#  generation, storage of secret codes
#


def _generage_2fa_code() -> str:
    return f"{1000 + secrets.randbelow(8999)}"  # code between [1000, 9999)


@log_decorator(log, level=logging.DEBUG)
async def set_2fa_code(
    app: web.Application,
    user_email: str,
    *,
    timeout: int = 60,
) -> str:
    redis_client = get_redis_validation_code_client(app)
    hash_key, code = user_email, _generage_2fa_code()
    await redis_client.set(hash_key, value=code, ex=timeout)
    return code


@log_decorator(log, level=logging.DEBUG)
async def get_2fa_code(app: web.Application, user_email: str) -> Optional[str]:
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
async def send_sms_code(phone_number: str, code: str, settings: TwilioSettings):
    # SEE https://www.twilio.com/docs/sms/quickstart/python
    def sender():
        log.info(
            "Sending sms code to %s",
            f"{phone_number=}",
        )
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            messaging_service_sid=settings.TWILIO_MESSAGING_SID,
            to=phone_number,
            body="Dear TI Planning Tool user, your verification code is {}".format(
                code
            ),
        )

        log.debug(
            "Got twilio client %s",
            f"{message=}",
        )

    await asyncio.get_event_loop().run_in_executor(None, sender)


#
# HELPERS
#


def mask_phone_number(phn: str) -> str:
    assert len(phn) > 10  # nosec
    return phn[:3] + len(phn[3:-2]) * "X" + phn[-2:]
