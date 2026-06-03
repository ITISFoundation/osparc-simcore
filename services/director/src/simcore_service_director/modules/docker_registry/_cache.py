import logging
from typing import Any, cast

from aiocache import Cache  # type: ignore[import-untyped]
from aiocache.base import BaseCache  # type: ignore[import-untyped]
from fastapi import FastAPI
from servicelib.logging_utils import log_context
from servicelib.redis._client import RedisClientSDK
from servicelib.redis._decorators import exclusive
from servicelib.redis._errors import CouldNotAcquireLockError
from servicelib.tracing import traced
from settings_library.redis import RedisDatabase

from ...core.settings import ApplicationSettings, get_application_settings
from ..redis import get_redis_client_manager
from ._client import ServiceType, list_services

_logger = logging.getLogger(__name__)

_REDIS_NAMESPACE: str = "director:registry_cache"
_REGISTRY_CACHE_REFRESH_MARKER_KEY: str = f"{_REDIS_NAMESPACE}:refresh_marker"
_REGISTRY_CACHE_REFRESH_LOCK_KEY: str = f"{_REDIS_NAMESPACE}:refresh_lock"


def create_registry_cache(app_settings: ApplicationSettings) -> BaseCache | None:
    if not app_settings.DIRECTOR_REGISTRY_CACHING:
        return None

    assert app_settings.DIRECTOR_REDIS is not None  # nosec
    assert Cache.REDIS is not None  # nosec
    redis_settings = app_settings.DIRECTOR_REDIS
    connection_pool_kwargs: dict[str, Any] = {}
    if redis_settings.REDIS_USER:
        connection_pool_kwargs["username"] = redis_settings.REDIS_USER

    return cast(
        BaseCache,
        Cache(
            Cache.REDIS,
            endpoint=redis_settings.REDIS_HOST,
            port=redis_settings.REDIS_PORT,
            db=int(RedisDatabase.AIOCACHE),
            password=(redis_settings.REDIS_PASSWORD.get_secret_value() if redis_settings.REDIS_PASSWORD else None),
            ssl=redis_settings.REDIS_SECURE,
            connection_pool_kwargs=connection_pool_kwargs if connection_pool_kwargs else None,
            namespace=app_settings.DIRECTOR_REGISTRY_CACHING_REDIS_NAMESPACE,
        ),
    )


def _get_redis_client_for_lock(app: FastAPI) -> RedisClientSDK:
    return get_redis_client_manager(app).client(database=RedisDatabase.LOCKS)


async def _is_cache_fresh(app: FastAPI) -> bool:
    """Check if cache freshness marker exists in Redis (skip refresh if fresh)."""
    app_settings = get_application_settings(app)
    if not app_settings.DIRECTOR_REGISTRY_CACHING:
        return False

    redis_manager = get_redis_client_manager(app)

    try:
        redis_client: RedisClientSDK = redis_manager.client(database=RedisDatabase.LOCKS)
        marker_exists = await redis_client.redis.exists(_REGISTRY_CACHE_REFRESH_MARKER_KEY)
        if marker_exists:
            _logger.debug("Cache freshness marker found, skipping refresh")
            return True
    except Exception:
        _logger.warning("Error checking cache freshness marker", exc_info=True)

    return False


async def _set_cache_fresh_marker(app: FastAPI) -> None:
    """Set cache freshness marker in Redis after successful refresh."""
    app_settings = get_application_settings(app)
    if not app_settings.DIRECTOR_REGISTRY_CACHING:
        return

    redis_manager = get_redis_client_manager(app)

    try:
        redis_client: RedisClientSDK = redis_manager.client(database=RedisDatabase.LOCKS)
        # Set marker TTL to half the cache TTL, so it expires if no refresh happens
        marker_ttl = int(app_settings.DIRECTOR_REGISTRY_CACHING_TTL.total_seconds())
        await redis_client.redis.setex(_REGISTRY_CACHE_REFRESH_MARKER_KEY, marker_ttl, "1")
        _logger.info("Cache freshness marker set with TTL=%s seconds", marker_ttl)
    except Exception:
        _logger.warning("Error setting cache freshness marker", exc_info=True)


@traced
@exclusive(
    redis_client=_get_redis_client_for_lock,
    lock_key=_REGISTRY_CACHE_REFRESH_LOCK_KEY,
    blocking=False,
)
async def _refresh_all_services_cache_locked(*, app: FastAPI) -> None:
    """Refresh cache (called with distributed lock from @exclusive decorator)."""
    with log_context(_logger, logging.INFO, msg="Updating cache with services (with lock)"):
        cache_is_fresh = await _is_cache_fresh(app)
        if not cache_is_fresh:
            await list_services(app, ServiceType.ALL, update_cache=True)
            # Mark cache as fresh after successful refresh
            await _set_cache_fresh_marker(app)


@traced
async def refresh_all_services_cache(*, app: FastAPI) -> None:
    """Refresh cache with distributed lock to prevent concurrent updates from multiple replicas."""
    try:
        await _refresh_all_services_cache_locked(app=app)
    except CouldNotAcquireLockError:
        _logger.debug("Another replica is refreshing cache, skipping this cycle")
