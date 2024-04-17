""" two-factor-authentication utils

Currently includes two parts:

- generation and storage of secret codes for 2FA validation (using redis)
- sending SMS of generated codes for validation (using twilio service)

"""

import asyncio
import logging

from aiohttp import web
from models_library.users import UserID
from pydantic import BaseModel, Field
from servicelib.error_codes import create_error_code
from servicelib.logging_utils import LogExtra, get_log_record_extra, log_decorator
from servicelib.utils_secrets import generate_passcode
from settings_library.twilio import TwilioSettings
from twilio.base.exceptions import TwilioException
from twilio.rest import Client

from ..login.errors import SendingVerificationEmailError, SendingVerificationSmsError
from ..products.api import Product
from ..redis import get_redis_validation_code_client
from .utils_email import get_template_path, send_email_from_template

log = logging.getLogger(__name__)


class ValidationCode(BaseModel):
    value: str = Field(..., description="The code")


#
# REDIS:
#  is used for generation and storage of secret codes
#
# SEE https://redis-py.readthedocs.io/en/stable/index.html


@log_decorator(log, level=logging.DEBUG)
async def _do_create_2fa_code(
    redis_client,
    user_email: str,
    *,
    expiration_seconds: int,
) -> str:
    hash_key: str = user_email
    code: str = generate_passcode()
    await redis_client.set(hash_key, value=code, ex=expiration_seconds)
    return code


async def create_2fa_code(
    app: web.Application, *, user_email: str, expiration_in_seconds: int
) -> str:
    """Saves 2FA code with an expiration time, i.e. a finite Time-To-Live (TTL)"""
    redis_client = get_redis_validation_code_client(app)
    code: str = await _do_create_2fa_code(
        redis_client=redis_client,
        user_email=user_email,
        expiration_seconds=expiration_in_seconds,
    )
    return code


@log_decorator(log, level=logging.DEBUG)
async def get_2fa_code(app: web.Application, user_email: str) -> str | None:
    """Returns 2FA code for user or None if it does not exist (e.g. expired or never set)"""
    redis_client = get_redis_validation_code_client(app)
    hash_key = user_email
    hash_value: str | None = await redis_client.get(hash_key)
    return hash_value


@log_decorator(log, level=logging.DEBUG)
async def delete_2fa_code(app: web.Application, user_email: str) -> None:
    redis_client = get_redis_validation_code_client(app)
    hash_key = user_email
    await redis_client.delete(hash_key)


#
# TWILIO
#   - sms service
#


class SMSError(RuntimeError):
    pass


@log_decorator(log, level=logging.DEBUG)
async def send_sms_code(
    phone_number: str,
    code: str,
    twilio_auth: TwilioSettings,
    twilio_messaging_sid: str,
    twilio_alpha_numeric_sender: str,
    first_name: str,
    user_id: UserID | None = None,
):
    try:
        create_kwargs = {
            "messaging_service_sid": twilio_messaging_sid,
            "to": phone_number,
            "body": f"Dear {first_name}, your verification code is {code}",
        }
        if twilio_auth.is_alphanumeric_supported(phone_number):
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
            client = Client(
                twilio_auth.TWILIO_ACCOUNT_SID, twilio_auth.TWILIO_AUTH_TOKEN
            )
            message = client.messages.create(**create_kwargs)

            log.debug(
                "Got twilio client %s",
                f"{message=}",
            )

        await asyncio.get_event_loop().run_in_executor(executor=None, func=_sender)

    except TwilioException as exc:
        error_code = create_error_code(exc)
        log_extra: LogExtra = get_log_record_extra(user_id=user_id) or {}
        log.exception(
            "Failed while setting up 2FA code and sending SMS to %s [%s]",
            mask_phone_number(phone_number),
            f"{error_code}",
            extra={"error_code": error_code, **log_extra},
        )
        raise SendingVerificationSmsError(reason=exc) from exc


#
# EMAIL
#


class EmailError(RuntimeError):
    pass


@log_decorator(log, level=logging.DEBUG)
async def send_email_code(
    request: web.Request,
    user_email: str,
    support_email: str,
    code: str,
    first_name: str,
    product: Product,
    user_id: UserID | None = None,
):
    try:
        email_template_path = await get_template_path(request, "new_2fa_code.jinja2")
        await send_email_from_template(
            request,
            from_=support_email,
            to=user_email,
            template=email_template_path,
            context={
                "host": request.host,
                "code": code,
                "name": first_name,
                "support_email": support_email,
                "product": product,
            },
        )
    except TwilioException as exc:
        error_code = create_error_code(exc)
        log_extra: LogExtra = get_log_record_extra(user_id=user_id) or {}
        log.exception(
            "Failed while setting up 2FA code and sending Email to %s [%s]",
            user_email,
            f"{error_code}",
            extra={"error_code": error_code, **log_extra},
        )
        raise SendingVerificationEmailError(reason=exc) from exc


#
# HELPERS
#

_FROM, _TO = 3, -1
_MIN_NUM_DIGITS = 5


def mask_phone_number(phone: str) -> str:
    assert len(phone) > _MIN_NUM_DIGITS  # nosec
    # SEE https://github.com/pydantic/pydantic/issues/1551
    # SEE https://en.wikipedia.org/wiki/E.164
    return phone[:_FROM] + len(phone[_FROM:_TO]) * "X" + phone[_TO:]
