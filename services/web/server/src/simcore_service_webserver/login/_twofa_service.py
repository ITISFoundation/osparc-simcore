"""two-factor-authentication utils

Currently includes two parts:

- generation and storage of secret codes for 2FA validation (using redis)
- sending SMS of generated codes for validation (using twilio service)

"""

import asyncio
import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from enum import StrEnum, auto
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
    """Generates a 2FA code and stores "<generation>:<digest>" with a finite TTL

    Returns the plaintext code. Trial counters are keyed by generation, so
    storing a code also starts a fresh trial budget.
    """
    redis_client = get_redis_validation_code_client(app)
    code: str = generate_passcode()
    generation = secrets.token_hex(_CODE_GENERATION_LENGTH // 2)
    await redis_client.set(
        user_email,
        value=f"{generation}:{_hash_2fa_code(app, code=code)}",
        ex=expiration_in_seconds,
    )
    return code


@log_decorator(log, level=logging.DEBUG)
async def has_2fa_code(app: web.Application, user_email: str) -> bool:
    """Returns True if a non-expired 2FA code exists for user_email"""
    redis_client = get_redis_validation_code_client(app)
    return await redis_client.get(user_email) is not None


@log_decorator(log, level=logging.DEBUG)
async def delete_2fa_code(app: web.Application, user_email: str) -> None:
    redis_client = get_redis_validation_code_client(app)
    hash_key = user_email
    await redis_client.delete(hash_key)


# Server-side 2FA attempt and resend state. The session-cookie counters in
# session.access_policies can be reset by replaying an old cookie, so these
# limits are kept in Redis.

_ATTEMPTS_KEY: Final[
    Annotated[str, doc("namespace for the trial counters, kept apart from the bare-email code keys")]
] = "2fa_attempts"

_RESEND_COOLDOWN_KEY: Final[
    Annotated[str, doc("namespace for the resend cooldown, kept apart from the bare-email code keys")]
] = "2fa_resend_cd"

_CODE_GENERATION_LENGTH: Final[
    Annotated[int, doc("length of the hex generation id stored alongside the code digest")]
] = 32

_STORED_CODE_LENGTH: Final[
    Annotated[int, doc("length of the stored value: generation, separator and HMAC-SHA256 hexdigest")]
] = _CODE_GENERATION_LENGTH + 1 + 64


class TrialOutcome(StrEnum):
    """Result of consuming one verification trial of the account's current code"""

    NO_CODE = auto()
    TRIALS_EXHAUSTED = auto()
    INVALID = auto()
    VALID = auto()


# script return codes of _CONSUME_TRIAL_SCRIPT
_NO_CODE: Final = 0
_TRIALS_EXHAUSTED: Final = 1
_TRIAL_CHARGED: Final = 2

# script return codes of _CONSUME_MATCHED_CODE_SCRIPT
_CODE_ALREADY_GONE: Final = 0
_CODE_CONSUMED: Final = 1


def _attempts_prefix(*, user_email: str) -> str:
    return f"{_ATTEMPTS_KEY}:{user_email}:"


def _attempts_key(*, user_email: str, generation: str) -> str:
    return f"{_attempts_prefix(user_email=user_email)}{generation}"


def _resend_cooldown_key(*, channel: str, user_email: str) -> str:
    return f"{_RESEND_COOLDOWN_KEY}:{channel}:{user_email}"


# Charges one trial and returns the stored value atomically, so a trial is only
# ever charged to the generation whose digest is then compared. INCR and PEXPIRE
# are in the same script, and the lifetime is copied from the code with
# PTTL/PEXPIRE, so a counter expires with its code to the millisecond and can
# never elapse early only to be recreated and refill the budget of a live code.
#
# KEYS[1] code key, KEYS[2] trial-counter prefix
# ARGV[1] max trials, ARGV[2] stored-value length, ARGV[3] generation length
# returns {0} no code, {1} budget spent, {2, stored value} trial charged
_CONSUME_TRIAL_SCRIPT: Final = """
    local stored = redis.call('GET', KEYS[1])
    if not stored or #stored ~= tonumber(ARGV[2]) then
        return {0}
    end
    local counter_key = KEYS[2] .. string.sub(stored, 1, tonumber(ARGV[3]))
    local trials = redis.call('INCR', counter_key)
    if trials == 1 then
        local pttl = redis.call('PTTL', KEYS[1])
        if pttl < 1 then
            pttl = 1
        end
        redis.call('PEXPIRE', counter_key, pttl)
    end
    if trials > tonumber(ARGV[1]) then
        return {1}
    end
    return {2, stored}
"""

# Deletes the code and reports whether it did, so the caller grants access only
# to the request that actually consumed the code. A replacement is never
# destroyed, and the counter belongs to one generation and is always safe to
# delete.
#
# KEYS[1] code key, KEYS[2] trial-counter key, ARGV[1] the matched stored value
# returns {1} consumed here, {0} replaced or already used
_CONSUME_MATCHED_CODE_SCRIPT: Final = """
    if redis.call('GET', KEYS[1]) == ARGV[1] then
        redis.call('DEL', KEYS[1])
        redis.call('DEL', KEYS[2])
        return 1
    end
    redis.call('DEL', KEYS[2])
    return 0
"""


@log_decorator(log, level=logging.DEBUG)
async def check_2fa_code(app: web.Application, *, user_email: str, code: str) -> TrialOutcome:
    """Consumes one trial of the account's current code and verifies against it

    The trial, the comparison and the destruction on a match are bound to one
    code generation, read atomically: late bookkeeping can neither verify nor
    delete a replacement, and the budget is spent before the comparison, so at
    most MAX_2FA_CODE_TRIALS verifications reach one code.

    Returns NO_CODE when no code is stored, TRIALS_EXHAUSTED when its budget is
    spent (then nothing is compared), INVALID when a trial was consumed by a
    wrong code, and VALID only when this call consumed the code, so concurrent
    submissions of the same code authenticate at most once.
    """
    redis_client = get_redis_validation_code_client(app)
    candidate_digest = _hash_2fa_code(app, code=code)

    consume_trial = redis_client.register_script(_CONSUME_TRIAL_SCRIPT)
    admitted = await consume_trial(
        keys=[user_email, _attempts_prefix(user_email=user_email)],
        args=[MAX_2FA_CODE_TRIALS, _STORED_CODE_LENGTH, _CODE_GENERATION_LENGTH],
    )
    assert isinstance(admitted, list)  # nosec
    if admitted[0] == _NO_CODE:
        return TrialOutcome.NO_CODE
    if admitted[0] == _TRIALS_EXHAUSTED:
        return TrialOutcome.TRIALS_EXHAUSTED
    assert admitted[0] == _TRIAL_CHARGED  # nosec

    stored_value: str = admitted[1]
    stored_digest = stored_value[_CODE_GENERATION_LENGTH + 1 :]
    if not are_secrets_equal(got=candidate_digest, expected=stored_digest):
        return TrialOutcome.INVALID

    generation = stored_value[:_CODE_GENERATION_LENGTH]
    consume_code = redis_client.register_script(_CONSUME_MATCHED_CODE_SCRIPT)
    consumed = await consume_code(
        keys=[user_email, _attempts_key(user_email=user_email, generation=generation)],
        args=[stored_value],
    )
    if consumed == _CODE_CONSUMED:
        return TrialOutcome.VALID
    return TrialOutcome.INVALID


@dataclass(frozen=True, kw_only=True, slots=True)
class ResendCooldown:
    """Outcome of arming the per-account resend cooldown.

    When retry_after_s is set, the window belongs to another request and this
    one must wait. Otherwise this request armed the window with its token and
    can release it again when the code turns out not to be sent.
    """

    user_email: str
    channel: str
    retry_after_s: int | None = None
    token: str | None = None


# Releases the cooldown only while this request still owns it, so a failed
# send cannot delete a window a later request armed.
#
# KEYS[1] cooldown key, ARGV[1] the token this request wrote
_COOLDOWN_RELEASE_SCRIPT: Final = """
    if redis.call('GET', KEYS[1]) == ARGV[1] then
        return redis.call('DEL', KEYS[1])
    end
    return 0
"""


@log_decorator(log, level=logging.DEBUG)
async def start_2fa_resend_cooldown(
    app: web.Application, *, user_email: str, channel: str, cooldown_in_seconds: int
) -> ResendCooldown:
    """Arms the per-account resend cooldown, or reports the remaining wait

    Arms atomically with SET NX, so concurrent resends race for one delivery.
    A request that does not send the code releases the window it armed, so a
    failed delivery does not lock the account out for a window that sent
    nothing.
    """
    redis_client = get_redis_validation_code_client(app)
    key = _resend_cooldown_key(channel=channel, user_email=user_email)
    token = secrets.token_hex(16)
    if await redis_client.set(key, token, ex=cooldown_in_seconds, nx=True):
        return ResendCooldown(user_email=user_email, channel=channel, token=token)
    remaining: int = await redis_client.ttl(key)
    return ResendCooldown(user_email=user_email, channel=channel, retry_after_s=max(remaining, 1))


@log_decorator(log, level=logging.DEBUG)
async def release_2fa_resend_cooldown(app: web.Application, cooldown: ResendCooldown) -> None:
    """Deletes a cooldown this request armed, leaving a re-armed window in place"""
    if cooldown.token is None:
        return
    redis_client = get_redis_validation_code_client(app)
    release = redis_client.register_script(_COOLDOWN_RELEASE_SCRIPT)
    await release(
        keys=[_resend_cooldown_key(channel=cooldown.channel, user_email=cooldown.user_email)],
        args=[cooldown.token],
    )


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
