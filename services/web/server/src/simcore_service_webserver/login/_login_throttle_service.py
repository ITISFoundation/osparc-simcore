"""Exponential back-off for repeated failed logins

Failures are counted per submitted email, whether or not the account exists, so
the back-off does not reveal which emails are registered.
"""

import asyncio
import contextlib
import hashlib
import ipaddress
import logging
import math
from collections.abc import AsyncIterator
from typing import Final

from aiohttp import web
from common_library.logging.logging_errors import create_troubleshooting_log_kwargs
from models_library.users import UserID
from redis.exceptions import LockError, RedisError

from . import _login_throttle_repository as _repository
from .errors import LoginThrottledError, LoginThrottleUnavailableError
from .settings import LoginThrottleSettings

_logger = logging.getLogger(__name__)

_MAX_BACKOFF_EXPONENT: Final[int] = 32
_REDIS_TIMEOUT_SEC: Final[int] = 5
_LOGIN_ATTEMPT_LOCK_TTL_SEC: Final[int] = 30
_LOGIN_ATTEMPT_LOCK_WAIT_SEC: Final[int] = 3  # below _REDIS_TIMEOUT_SEC

type ClientIP = ipaddress.IPv4Address | ipaddress.IPv6Address


def parse_client_ip(x_forwarded_for: str | None, *, settings: LoginThrottleSettings) -> ClientIP | None:
    """The X-Forwarded-For entry at LOGIN_THROTTLE_CLIENT_IP_DEPTH from the right, or None if absent or malformed

    Entries to the left of it can be forged by the client
    """
    if not x_forwarded_for:
        return None
    entries = x_forwarded_for.split(",")
    depth = settings.LOGIN_THROTTLE_CLIENT_IP_DEPTH
    if len(entries) < depth:
        return None
    try:
        return ipaddress.ip_address(entries[-depth].strip())
    except ValueError:
        return None


def is_trusted_client(client_ip: ClientIP | None, *, settings: LoginThrottleSettings) -> bool:
    return client_ip is not None and any(client_ip in network for network in settings.LOGIN_THROTTLE_TRUSTED_NETWORKS)


@contextlib.asynccontextmanager
async def _handle_redis_errors() -> AsyncIterator[None]:
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
        raise LoginThrottleUnavailableError from err


@contextlib.asynccontextmanager
async def exclusive_login_attempt(app: web.Application, *, email: str) -> AsyncIterator[None]:
    """Serializes password verification per email, so that concurrent attempts
    cannot slip past a back-off that an earlier attempt triggers.

    Raises:
        LoginThrottledError: if other attempts for this email keep the lock for too long
        LoginThrottleUnavailableError: if redis fails
    """
    lock = _repository.get_login_attempt_lock(
        app,
        digest=_get_digest(email),
        ttl_sec=_LOGIN_ATTEMPT_LOCK_TTL_SEC,
        wait_sec=_LOGIN_ATTEMPT_LOCK_WAIT_SEC,
    )
    async with _handle_redis_errors():
        acquired = await lock.acquire()
    if not acquired:
        raise LoginThrottledError(retry_after_sec=1)

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
    async with _handle_redis_errors():
        ttl_ms = await _repository.get_block_ttl_ms(app, digest=_get_digest(email))
    return math.ceil(ttl_ms / 1000)


async def raise_if_login_throttled(app: web.Application, *, email: str) -> None:
    """
    Raises:
        LoginThrottledError: while the email is in back-off
        LoginThrottleUnavailableError: if redis fails
    """
    retry_after_sec = await get_login_retry_after_sec(app, email=email)
    if retry_after_sec > 0:
        raise LoginThrottledError(retry_after_sec=retry_after_sec)


async def register_failed_login(
    app: web.Application, *, email: str, user_id: UserID | None = None, settings: LoginThrottleSettings
) -> None:
    digest = _get_digest(email)
    async with _handle_redis_errors():
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
