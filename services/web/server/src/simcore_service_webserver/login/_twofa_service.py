"""two-factor-authentication utils

Currently includes two parts:

- generation and storage of secret codes for 2FA validation (using redis)
- sending SMS of generated codes for validation (using twilio service)

"""

import asyncio
import hashlib
import hmac
import logging

import twilio.rest  # type: ignore[import-untyped]
from aiohttp import web
from common_library.gettext_support import SupportedLocale, get_translator
from common_library.user_messages import user_message
from models_library.notifications import Channel
from models_library.products import ProductName
from models_library.users import UserID
from pydantic import BaseModel, Field
from servicelib.logging_utils import log_decorator
from servicelib.utils_secrets import are_secrets_equal, generate_passcode
from settings_library.twilio import TwilioSettings
from twilio.base.exceptions import TwilioException  # type: ignore[import-untyped]

from ..locale import resolve_effective_locale
from ..notifications import notifications_service
from ..notifications.models import EmailContact
from ..redis import get_redis_validation_code_client
from ..session.settings import get_plugin_settings as get_session_settings
from .errors import SendingVerificationEmailError, SendingVerificationSmsError

log = logging.getLogger(__name__)


class ValidationCode(BaseModel):
    value: str = Field(..., description="The code")


#
# REDIS:
#  is used for generation and storage of secret codes
#
# SEE https://redis-py.readthedocs.io/en/stable/index.html


def hash_2fa_code_for_storage(*, code: str, secret_key: str) -> str:
    """Returns the HMAC-SHA256 digest used to persist one time pads in Redis."""
    return hmac.new(
        key=secret_key.encode(),
        msg=code.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()


def _hash_2fa_code(app: web.Application, *, code: str) -> str:
    """HMAC-SHA256 of the OTP so that only a non-reversible digest (never the
    plaintext code) is persisted in Redis. Keyed with the server-side session secret.
    """
    secret_key = get_session_settings(app).SESSION_SECRET_KEY.get_secret_value()
    return hash_2fa_code_for_storage(code=code, secret_key=secret_key)


@log_decorator(log, level=logging.DEBUG)
async def create_2fa_code(app: web.Application, *, user_email: str, expiration_in_seconds: int) -> str:
    """Generates a 2FA code, stores only its HMAC digest with a finite TTL and returns the plaintext code"""
    redis_client = get_redis_validation_code_client(app)
    code: str = generate_passcode()
    await redis_client.set(
        user_email,
        value=_hash_2fa_code(app, code=code),
        ex=expiration_in_seconds,
    )
    return code


@log_decorator(log, level=logging.DEBUG)
async def has_2fa_code(app: web.Application, user_email: str) -> bool:
    """Returns True if a non-expired 2FA code exists for user_email"""
    redis_client = get_redis_validation_code_client(app)
    return await redis_client.get(user_email) is not None


@log_decorator(log, level=logging.DEBUG)
async def verify_2fa_code(app: web.Application, *, user_email: str, code: str) -> bool:
    """Constant-time verification of a submitted 2FA code against the stored HMAC digest"""
    redis_client = get_redis_validation_code_client(app)
    stored_digest: str | None = await redis_client.get(user_email)
    if stored_digest is None:
        return False
    return are_secrets_equal(got=_hash_2fa_code(app, code=code), expected=stored_digest)


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
    app: web.Application,
    *,
    phone_number: str,
    code: str,
    twilio_auth: TwilioSettings,
    twilio_messaging_sid: str,
    twilio_alpha_numeric_sender: str,
    first_name: str,
    user_id: UserID | None = None,
    locale: SupportedLocale | None = None,
):
    try:
        resolved_locale = await resolve_effective_locale(
            app,
            user_id=user_id,
            locale=locale,
        )
        translator = get_translator(resolved_locale)
        create_kwargs = {
            "messaging_service_sid": twilio_messaging_sid,
            "to": phone_number,
            "body": translator.gettext(
                user_message(
                    "Dear {first_name}, your verification code is {code}",
                    _hint="SMS message of at most 70 characters",
                    _version=1,
                )
            ).format(first_name=first_name[:15], code=code),
        }
        if twilio_auth.is_alphanumeric_supported(phone_number):
            create_kwargs["from_"] = twilio_alpha_numeric_sender

        def _sender():
            log.info(
                "Sending sms code to %s",
                mask_phone_number(phone_number),
            )
            #
            # SEE https://www.twilio.com/docs/sms/quickstart/python
            #
            # NOTE: this is mocked
            client = twilio.rest.Client(
                twilio_auth.TWILIO_ACCOUNT_SID,
                twilio_auth.TWILIO_AUTH_TOKEN.get_secret_value(),
            )
            message = client.messages.create(**create_kwargs)

            log.debug(
                "Got twilio client %s",
                f"{message=}",
            )

        await asyncio.get_event_loop().run_in_executor(executor=None, func=_sender)

    except TwilioException as exc:
        raise SendingVerificationSmsError(
            details=f"Could not send SMS to {mask_phone_number(phone_number)}",
            user_id=user_id,
            twilio_error=exc,
        ) from exc


#
# EMAIL
#


class EmailError(RuntimeError):
    pass


@log_decorator(log, level=logging.DEBUG)
async def send_email_code(
    app: web.Application,
    *,
    user_email: str,
    code: str,
    first_name: str,
    user_name: str,
    product_name: ProductName,
    host: str,
    ttl: int,
    user_id: UserID | None = None,
    locale: SupportedLocale | None = None,
):
    try:
        await notifications_service.send_message_from_template(
            app,
            user_id=user_id,
            product_name=product_name,
            channel=Channel.email,
            group_ids=None,
            external_contacts=[
                EmailContact(
                    name=first_name,
                    email=user_email,
                )
            ],
            template_name="new_2fa_code",
            context={
                "user": {
                    "first_name": first_name,
                    "user_name": user_name,
                },
                "host": host,
                "code": code,
                "ttl": ttl,
            },
            locale=locale,
        )
    except Exception as exc:
        raise SendingVerificationEmailError(
            details=f"Could not send email to {user_email}",
            user_id=user_id,
            user_email=user_email,
            email_error=exc,
        ) from exc


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
