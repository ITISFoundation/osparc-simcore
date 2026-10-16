"""Exponential back-off for repeated failed logins

Failures are counted per submitted email, whether or not the account exists, so
the back-off does not reveal which emails are registered.
"""

import contextlib
import hashlib
import logging
import math
from collections.abc import Iterator

from aiohttp import web
from common_library.logging.logging_errors import create_troubleshooting_log_kwargs
from redis.exceptions import RedisError

from ..utils_rate_limiting import create_too_many_requests_error
from . import _login_throttle_repository as _repository
from .constants import MSG_LOGIN_TOO_MANY_ATTEMPTS, MSG_LOGIN_UNAVAILABLE
from .settings import LoginSettings

_logger = logging.getLogger(__name__)

_MAX_BACKOFF_EXPONENT = 32


@contextlib.contextmanager
def _handle_redis_errors_as_503() -> Iterator[None]:
    try:
        yield
    except RedisError as err:
        _logger.exception(
            **create_troubleshooting_log_kwargs(
                f"{MSG_LOGIN_UNAVAILABLE}: login throttle unavailable due to redis error.",
                error=err,
                tip="Check redis connection",
            )
        )
        raise web.HTTPServiceUnavailable(text=MSG_LOGIN_UNAVAILABLE) from err


def _get_digest(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()


def compute_delay_sec(failures: int, *, settings: LoginSettings) -> int:
    """Delay after the `failures`-th consecutive failure: doubles with each failure, up to the maximum"""
    excess = failures - settings.LOGIN_THROTTLE_FREE_FAILED_ATTEMPTS
    if excess <= 0:
        return 0
    return min(
        settings.LOGIN_THROTTLE_MAX_DELAY_SEC,
        settings.LOGIN_THROTTLE_BASE_DELAY_SEC * 2 ** min(excess - 1, _MAX_BACKOFF_EXPONENT),
    )


async def get_login_retry_after_sec(app: web.Application, *, email: str) -> int:
    """Seconds until the next login attempt is allowed for this email (0 if allowed now)"""
    with _handle_redis_errors_as_503():
        ttl_ms = await _repository.get_block_ttl_ms(app, digest=_get_digest(email))
    return math.ceil(ttl_ms / 1000)


async def raise_if_login_throttled(app: web.Application, *, email: str) -> None:
    """
    Raises:
        web.HTTPTooManyRequests: while the email is in back-off
    """
    retry_after_sec = await get_login_retry_after_sec(app, email=email)
    if retry_after_sec > 0:
        raise create_too_many_requests_error(
            retry_after_sec=retry_after_sec,
            error_msg=MSG_LOGIN_TOO_MANY_ATTEMPTS,
        )


async def register_failed_login(app: web.Application, *, email: str, settings: LoginSettings) -> None:
    digest = _get_digest(email)
    with _handle_redis_errors_as_503():
        failures = await _repository.increment_failures(
            app, digest=digest, window_sec=settings.LOGIN_THROTTLE_WINDOW_SEC
        )
        delay_sec = compute_delay_sec(failures, settings=settings)
        if delay_sec > 0:
            await _repository.block(app, digest=digest, duration_ms=delay_sec * 1000)
        _logger.warning("Login back-off applied: failures=%d delay_sec=%d digest=%s", failures, delay_sec, digest[:8])


async def clear_failed_logins(app: web.Application, *, email: str) -> None:
    with _handle_redis_errors_as_503():
        await _repository.clear(app, digest=_get_digest(email))
