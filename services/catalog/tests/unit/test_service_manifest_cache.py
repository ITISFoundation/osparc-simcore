# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from contextlib import suppress
from typing import Any
from unittest.mock import Mock

from aiocache.base import BaseCache  # type: ignore[import-untyped]
from fastapi import FastAPI
from models_library.services_metadata_published import ServiceMetaDataPublished
from settings_library.redis import RedisDatabase, RedisSettings
from simcore_service_catalog.service.manifest_cache import (
    _manifest_cache_lifespan,
    create_service_manifest_cache,
    get_service_manifest_cache,
)

pytest_simcore_core_services_selection = ["redis"]


async def test_manifest_cache_lifespan_roundtrips_metadata_through_redis(
    redis_settings: RedisSettings,
    expected_director_rest_api_list_services: list[dict[str, Any]],
):
    app = FastAPI()
    app.state.settings = Mock(CATALOG_REDIS=redis_settings)

    lifespan = _manifest_cache_lifespan(app)
    await anext(lifespan)

    service_cache = get_service_manifest_cache(app)
    expected_service = ServiceMetaDataPublished.model_validate(expected_director_rest_api_list_services[0])
    cache_key = "test/manifest_cache_roundtrip"

    assert await service_cache.set(cache_key, expected_service.model_dump(mode="json", by_alias=True), ttl=60)
    assert ServiceMetaDataPublished.model_validate(await service_cache.get(cache_key)) == expected_service
    await service_cache.delete(cache_key)

    with suppress(StopAsyncIteration):
        await anext(lifespan)

    assert app.state.service_manifest_cache is None


async def test_create_service_manifest_cache_targets_the_aiocache_database(redis_settings: RedisSettings):
    service_cache: BaseCache = create_service_manifest_cache(redis_settings)
    try:
        assert service_cache.namespace == "catalog:service_manifest:v1"
        assert service_cache.db == int(RedisDatabase.AIOCACHE)
        assert service_cache.endpoint == redis_settings.REDIS_HOST
        assert service_cache.port == redis_settings.REDIS_PORT
    finally:
        await service_cache.close()
