from collections.abc import AsyncIterator

from aiocache import SimpleMemoryCache  # type: ignore[import-untyped]
from aiocache.base import BaseCache  # type: ignore[import-untyped]
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State


def create_service_manifest_cache() -> BaseCache:
    return SimpleMemoryCache(namespace=__name__)


async def manifest_cache_lifespan(app: FastAPI) -> AsyncIterator[State]:
    service_manifest_cache = create_service_manifest_cache()
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


def configure_manifest_cache(app_lifespan: LifespanManager) -> None:
    app_lifespan.add(manifest_cache_lifespan)
