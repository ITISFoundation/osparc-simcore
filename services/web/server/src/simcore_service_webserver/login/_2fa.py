""" two-factor-authentication utils

Currently includes two parts:

- generation and storage of secret codes for 2FA validation (using redis)
- sending SMS of generated codes for validation (using twilio service)

"""

import asyncio
import logging
import os
import secrets
from typing import Optional

from aiohttp import web
from pydantic import BaseModel, Field
from servicelib.logging_utils import log_decorator
from twilio.rest import Client

from ..redis import get_redis_validation_code_client

log = logging.getLogger(__name__)


class ValidationCode(BaseModel):
    value: str = Field(..., description="The code")


#
# REDIS:
#  generation, storage of secret codes
#


async def _generage_code() -> int:
    return 1000 + secrets.randbelow(8999)  # code between [1000, 9999)


@log_decorator(log, level=logging.DEBUG)
async def add_validation_code(
    app: web.Application, user_email: str, *, timeout: int = 60
):
    redis_client = get_redis_validation_code_client(app)
    hash_key = user_email
    code = _generage_code()
    await redis_client.set(hash_key, code, ex=timeout)
    return code


@log_decorator(log, level=logging.DEBUG)
async def get_validation_code(app: web.Application, user_email: str) -> Optional[str]:
    redis_client = get_redis_validation_code_client(app)
    hash_key = user_email
    return await redis_client.get(hash_key)


@log_decorator(log, level=logging.DEBUG)
async def delete_validation_code(app: web.Application, user_email: str) -> None:
    redis_client = get_redis_validation_code_client(app)
    hash_key = user_email
    await redis_client.delete(hash_key)


#
# TWILIO
#   - sms service
#


async def send_sms_code(phone_number: str, code: str):
    # SEE https://www.twilio.com/docs/sms/quickstart/python
    def sender():
        log.info(
            "sending sms code to %s",
            f"{phone_number=}",
        )

        account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        messaging_service_sid = os.environ.get("TWILIO_MESSAGING_SID")

        client = Client(account_sid, auth_token)
        message = client.messages.create(
            messaging_service_sid=messaging_service_sid,
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
