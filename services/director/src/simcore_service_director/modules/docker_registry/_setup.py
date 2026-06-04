from collections.abc import AsyncIterator

from common_library.async_tools import cancel_wait_task
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.background_task import create_periodic_task

from ...core.settings import get_application_settings
from ._cache import create_registry_cache, refresh_all_services_cache
from ._client import setup_registry_connection


async def registry_lifespan(app: FastAPI) -> AsyncIterator[State]:
    app_settings = get_application_settings(app)
    cache = create_registry_cache(app_settings)
    app.state.registry_cache_memory = cache
    await setup_registry_connection(app)
    app.state.auto_cache_task = None
    if app_settings.DIRECTOR_REGISTRY_CACHING:
        app.state.auto_cache_task = create_periodic_task(
            refresh_all_services_cache,
            interval=app_settings.DIRECTOR_REGISTRY_CACHING_TTL / 4,
            task_name="director-auto-cache-task",
            app=app,
        )
    try:
        yield {}
    finally:
        if app.state.auto_cache_task:
            await cancel_wait_task(app.state.auto_cache_task)
        if app.state.registry_cache_memory:
            await app.state.registry_cache_memory.close()


def configure_registry_lifespans(
    app_lifespan: LifespanManager[FastAPI],
) -> None:
    app_lifespan.add(registry_lifespan)
