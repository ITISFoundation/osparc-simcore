"""Exponential back-off for repeated failed logins

Failures are counted per submitted email, whether or not the account exists, so
the back-off does not reveal which emails are registered.
"""

import asyncio
import contextlib
import hashlib
import logging
import math
from collections.abc import AsyncIterator

from aiohttp import web
from common_library.logging.logging_errors import create_troubleshooting_log_kwargs
from models_library.users import UserID
from redis.exceptions import LockError, RedisError

from ..utils_rate_limiting import create_too_many_requests_error
from . import _login_throttle_repository as _repository
from .constants import MSG_LOGIN_TOO_MANY_ATTEMPTS, MSG_LOGIN_UNAVAILABLE
from .settings import LoginThrottleSettings

_logger = logging.getLogger(__name__)

_MAX_BACKOFF_EXPONENT = 32
_REDIS_TIMEOUT_SEC = 5
_LOGIN_ATTEMPT_LOCK_TTL_SEC = 30
_LOGIN_ATTEMPT_LOCK_WAIT_SEC = 3  # below _REDIS_TIMEOUT_SEC


@contextlib.asynccontextmanager
async def _handle_redis_errors_as_503() -> AsyncIterator[None]:
    try:
        async with asyncio.timeout(_REDIS_TIMEOUT_SEC):
            yield
    except (RedisError, TimeoutError) as err:
        _logger.exception(
            **create_troubleshooting_log_kwargs(
                "Login throttle unavailable due to redis error",
                error=err,
                tip="Check redis connection",
            )
        )
        raise web.HTTPServiceUnavailable(text=MSG_LOGIN_UNAVAILABLE) from err


@contextlib.asynccontextmanager
async def exclusive_login_attempt(app: web.Application, *, email: str) -> AsyncIterator[None]:
    """Serializes password verification per email, so that concurrent attempts
    cannot slip past a back-off that an earlier attempt triggers.

    Raises:
        web.HTTPTooManyRequests: if other attempts for this email keep the lock for too long
    """
    lock = _repository.get_login_attempt_lock(
        app,
        digest=_get_digest(email),
        ttl_sec=_LOGIN_ATTEMPT_LOCK_TTL_SEC,
        wait_sec=_LOGIN_ATTEMPT_LOCK_WAIT_SEC,
    )
    async with _handle_redis_errors_as_503():
        acquired = await lock.acquire()
    if not acquired:
        raise create_too_many_requests_error(retry_after_sec=1, error_msg=MSG_LOGIN_TOO_MANY_ATTEMPTS)

    try:
        yield
    finally:
        try:
            async with asyncio.timeout(_REDIS_TIMEOUT_SEC):
                await lock.release()
        except (LockError, RedisError, TimeoutError) as err:
            _logger.exception(
                **create_troubleshooting_log_kwargs(
                    "Could not release the login attempt lock, it expires by itself",
                    error=err,
                    tip="Check redis connection",
                )
            )


def _get_digest(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()


def compute_delay_sec(failures: int, *, settings: LoginThrottleSettings) -> int:
    """Delay after the `failures`-th consecutive failure: doubles with each failure, up to the maximum"""
    excess = failures - settings.LOGIN_THROTTLE_FREE_FAILED_ATTEMPTS
    if excess <= 0:
        return 0
    return min(
        settings.LOGIN_THROTTLE_MAX_DELAY_SEC,
        settings.LOGIN_THROTTLE_BASE_DELAY_SEC * (1 << min(excess - 1, _MAX_BACKOFF_EXPONENT)),
    )


async def get_login_retry_after_sec(app: web.Application, *, email: str) -> int:
    """Seconds until the next login attempt is allowed for this email (0 if allowed now)"""
    async with _handle_redis_errors_as_503():
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


async def register_failed_login(
    app: web.Application, *, email: str, user_id: UserID | None = None, settings: LoginThrottleSettings
) -> None:
    digest = _get_digest(email)
    async with _handle_redis_errors_as_503():
        failures = await _repository.increment_failures(
            app, digest=digest, window_sec=settings.LOGIN_THROTTLE_WINDOW_SEC
        )
        delay_sec = compute_delay_sec(failures, settings=settings)
        if delay_sec > 0:
            await _repository.block(app, digest=digest, duration_ms=delay_sec * 1000)
            # user_id is logged (not stored) only to help ops identify an account under
            # attack; it does not affect the throttle key or the response to the caller,
            # so known and unknown emails remain indistinguishable from the outside
            _logger.warning(
                "Login back-off applied: failures=%d delay_sec=%d digest=%s user_id=%s",
                failures,
                delay_sec,
                digest[:8],
                user_id if user_id is not None else "unknown",
            )


async def clear_failed_logins(app: web.Application, *, email: str) -> None:
    """Best effort: the user is already authenticated and a stale counter expires by itself"""
    try:
        async with asyncio.timeout(_REDIS_TIMEOUT_SEC):
            await _repository.clear(app, digest=_get_digest(email))
    except (RedisError, TimeoutError) as err:
        _logger.exception(
            **create_troubleshooting_log_kwargs(
                "Could not clear failed login counter after a successful login",
                error=err,
                tip="Check redis connection",
            )
        )
