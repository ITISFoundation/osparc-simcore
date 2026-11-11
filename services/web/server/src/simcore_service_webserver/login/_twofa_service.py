"""two-factor-authentication utils

Currently includes two parts:

- generation and storage of secret codes for 2FA validation (using redis)
- sending SMS of generated codes for validation (using twilio service)

"""

import asyncio
import hashlib
import hmac
import logging
from typing import Annotated, Final

import twilio.rest  # type: ignore[import-untyped]
from aiohttp import web
from annotated_types import doc
from common_library.gettext_support import SupportedLocale, get_translator
from common_library.user_messages import user_message
from models_library.notifications import Channel
from models_library.products import ProductName
from models_library.users import UserID
from pydantic import BaseModel, Field, SecretStr
from servicelib.logging_utils import log_decorator
from servicelib.utils_secrets import are_secrets_equal, generate_passcode
from settings_library.twilio import TwilioSettings
from twilio.base.exceptions import TwilioException  # type: ignore[import-untyped]

from ..locale import resolve_effective_locale
from ..notifications import notifications_service
from ..notifications.models import EmailContact
from ..redis import get_redis_validation_code_client
from ..session.settings import get_plugin_settings as get_session_settings
from .constants import MAX_2FA_CODE_TRIALS
from .errors import SendingVerificationEmailError, SendingVerificationSmsError

log = logging.getLogger(__name__)


class ValidationCode(BaseModel):
    value: str = Field(..., description="The code")


#
# REDIS:
#  is used for generation and storage of secret codes
#
# SEE https://redis-py.readthedocs.io/en/stable/index.html


def hash_2fa_code_for_storage(*, code: str, secret_key: SecretStr) -> str:
    """Returns the HMAC-SHA256 digest used to persist one time pads in Redis."""
    return hmac.new(
        key=secret_key.get_secret_value().encode(),
        msg=code.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()


def _hash_2fa_code(app: web.Application, *, code: str) -> str:
    """HMAC-SHA256 of the OTP so that only a non-reversible digest (never the
    plaintext code) is persisted in Redis. Keyed with the server-side session secret.
    """
    return hash_2fa_code_for_storage(code=code, secret_key=get_session_settings(app).SESSION_SECRET_KEY)


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


# Server-side 2FA attempt and resend state. The session-cookie counters in
# session.access_policies can be reset by replaying an old cookie, so these
# limits are kept in Redis and keyed by account.

_ATTEMPTS_KEY: Final[
    Annotated[str, doc("namespace for the trial counter, kept apart from the bare-email code keys")]
] = "2fa_attempts"

_RESEND_COOLDOWN_KEY: Final[
    Annotated[str, doc("namespace for the resend cooldown, kept apart from the bare-email code keys")]
] = "2fa_resend_cd"


def _attempts_key(user_email: str) -> str:
    return f"{_ATTEMPTS_KEY}:{user_email}"


def _resend_cooldown_key(*, channel: str, user_email: str) -> str:
    return f"{_RESEND_COOLDOWN_KEY}:{channel}:{user_email}"


@log_decorator(log, level=logging.DEBUG)
async def consume_2fa_attempt(app: web.Application, *, user_email: str, ttl: int) -> bool:
    """Consumes one code-verification trial of an account, before the code is checked.

    The budget belongs to the current code: the counter lives in Redis keyed
    by account, is incremented atomically and expires with the code's
    lifetime. Callers verify only when this returns True, so no more than
    MAX_2FA_CODE_TRIALS verifications can reach the stored code, whatever the
    concurrency or the client-held session cookies.

    Returns False when the budget is exhausted.
    """
    redis_client = get_redis_validation_code_client(app)
    key = _attempts_key(user_email)
    attempts = await redis_client.incr(key)
    if attempts == 1:
        await redis_client.expire(key, ttl)
    return attempts <= MAX_2FA_CODE_TRIALS


@log_decorator(log, level=logging.DEBUG)
async def clear_2fa_attempts(app: web.Application, *, user_email: str) -> None:
    """Forgets the trial counter of an account, e.g. when a new code is issued"""
    redis_client = get_redis_validation_code_client(app)
    await redis_client.delete(_attempts_key(user_email))


@log_decorator(log, level=logging.DEBUG)
async def start_2fa_resend_cooldown(
    app: web.Application, *, user_email: str, channel: str, cooldown_in_seconds: int
) -> int | None:
    """Starts the per-account resend cooldown, or reports the remaining wait.

    The cooldown is started atomically for the request, not for the delivery:
    it is consumed even if sending the code fails afterwards.

    Returns None when the resend is allowed now, or the seconds left to wait.
    """
    redis_client = get_redis_validation_code_client(app)
    key = _resend_cooldown_key(channel=channel, user_email=user_email)
    if await redis_client.set(key, "1", ex=cooldown_in_seconds, nx=True):
        return None
    remaining = await redis_client.ttl(key)
    return max(remaining, 1)


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
