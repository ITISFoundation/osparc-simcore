from collections.abc import AsyncIterator
from typing import Any, Final

from aiocache.backends.redis import RedisCache  # type: ignore[import-untyped]
from aiocache.base import BaseCache  # type: ignore[import-untyped]
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.fastapi.redis_lifespan import configure_redis_client_sdk
from servicelib.redis import RedisClientSDK
from settings_library.redis import RedisDatabase, RedisSettings

from .._meta import APP_NAME

_CACHE_NAMESPACE: Final[str] = "catalog:service_manifest:v1"
_LOCK_CLIENT_STATE_ATTR: Final[str] = "service_manifest_lock_client"


def create_service_manifest_cache(redis_settings: RedisSettings) -> BaseCache:
    connection_pool_kwargs: dict[str, Any] = {}
    if redis_settings.REDIS_USER:
        connection_pool_kwargs["username"] = redis_settings.REDIS_USER

    return RedisCache(
        endpoint=redis_settings.REDIS_HOST,
        port=redis_settings.REDIS_PORT,
        db=int(RedisDatabase.AIOCACHE),
        password=(redis_settings.REDIS_PASSWORD.get_secret_value() if redis_settings.REDIS_PASSWORD else None),
        ssl=redis_settings.REDIS_SECURE,
        connection_pool_kwargs=connection_pool_kwargs if connection_pool_kwargs else None,
        namespace=_CACHE_NAMESPACE,
    )


async def _manifest_cache_lifespan(app: FastAPI) -> AsyncIterator[State]:
    service_manifest_cache = create_service_manifest_cache(app.state.settings.CATALOG_REDIS)
    app.state.service_manifest_cache = service_manifest_cache
    try:
        yield {}
    finally:
        await service_manifest_cache.close()
        app.state.service_manifest_cache = None


def get_service_manifest_cache(app: FastAPI) -> BaseCache:
    service_manifest_cache: BaseCache | None = app.state.service_manifest_cache
    assert service_manifest_cache is not None  # nosec
    return service_manifest_cache


def get_service_manifest_lock_client(app: FastAPI) -> RedisClientSDK | None:
    return getattr(app.state, _LOCK_CLIENT_STATE_ATTR, None)


def configure_manifest_cache(
    app_lifespan: LifespanManager[FastAPI],
    *,
    settings: RedisSettings,
) -> None:
    configure_redis_client_sdk(
        app_lifespan,
        settings=settings,
        database=RedisDatabase.LOCKS,
        client_name=APP_NAME,
        app_state_attr=_LOCK_CLIENT_STATE_ATTR,
    )
    app_lifespan.add(_manifest_cache_lifespan)
