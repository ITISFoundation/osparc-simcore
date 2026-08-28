from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import Mock

from aiocache.backends.redis import RedisCache  # type: ignore[import-untyped]
from aiocache.serializers import JsonSerializer  # type: ignore[import-untyped]
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from settings_library.redis import RedisDatabase, RedisSettings
from simcore_service_catalog.service.manifest_cache import (
    _manifest_cache_lifespan,
    configure_manifest_cache,
    create_service_manifest_cache,
    get_service_manifest_cache,
)

pytest_simcore_core_services_selection = [
    "redis",
]


async def test_manifest_cache_lifespan():
    app = FastAPI()
    app.state.settings = SimpleNamespace(CATALOG_REDIS=RedisSettings())

    async with asynccontextmanager(_manifest_cache_lifespan)(app) as state:
        assert state == {}
        service_manifest_cache = get_service_manifest_cache(app)
        assert isinstance(service_manifest_cache, RedisCache)

    assert app.state.service_manifest_cache is None


def test_configure_manifest_cache():
    app_lifespan = Mock(spec=LifespanManager)

    configure_manifest_cache(app_lifespan)

    app_lifespan.add.assert_called_once_with(_manifest_cache_lifespan)


async def test_create_service_manifest_cache():
    redis_settings = RedisSettings()
    service_manifest_cache = create_service_manifest_cache(redis_settings)
    try:
        assert isinstance(service_manifest_cache, RedisCache)
        assert service_manifest_cache.db == RedisDatabase.AIOCACHE
        assert service_manifest_cache.endpoint == redis_settings.REDIS_HOST
        assert service_manifest_cache.port == redis_settings.REDIS_PORT
        assert isinstance(service_manifest_cache.serializer, JsonSerializer)
    finally:
        await service_manifest_cache.close()


async def test_service_manifest_cache_is_shared(redis_service: RedisSettings):
    first_cache = create_service_manifest_cache(redis_service)
    second_cache = create_service_manifest_cache(redis_service)
    try:
        await first_cache.clear()
        assert await first_cache.set("shared-key", {"value": "from-first-replica"}, ttl=60)

        assert await second_cache.get("shared-key") == {"value": "from-first-replica"}
    finally:
        await first_cache.clear()
        await first_cache.close()
        await second_cache.close()
