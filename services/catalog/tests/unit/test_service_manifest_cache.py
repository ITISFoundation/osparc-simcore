from contextlib import asynccontextmanager
from unittest.mock import Mock

from aiocache import SimpleMemoryCache  # type: ignore[import-untyped]
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from simcore_service_catalog.service.manifest_cache import (
    configure_manifest_cache,
    create_service_manifest_cache,
    get_service_manifest_cache,
    manifest_cache_lifespan,
)


async def test_manifest_cache_lifespan():
    app = FastAPI()

    async with asynccontextmanager(manifest_cache_lifespan)(app) as state:
        assert state == {}
        service_manifest_cache = get_service_manifest_cache(app)
        assert isinstance(service_manifest_cache, SimpleMemoryCache)

    assert app.state.service_manifest_cache is None


def test_configure_manifest_cache():
    app_lifespan = Mock(spec=LifespanManager)

    configure_manifest_cache(app_lifespan)

    app_lifespan.add.assert_called_once_with(manifest_cache_lifespan)


async def test_create_service_manifest_cache():
    service_manifest_cache = create_service_manifest_cache()
    try:
        assert isinstance(service_manifest_cache, SimpleMemoryCache)
    finally:
        await service_manifest_cache.close()
