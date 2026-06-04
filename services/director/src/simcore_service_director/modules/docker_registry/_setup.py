from common_library.async_tools import cancel_wait_task
from fastapi import FastAPI
from servicelib.background_task import create_periodic_task

from ...core.settings import get_application_settings
from ._cache import create_registry_cache, refresh_all_services_cache
from ._client import setup_registry_connection


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
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

    async def on_shutdown() -> None:
        if app.state.auto_cache_task:
            await cancel_wait_task(app.state.auto_cache_task)
        if app.state.registry_cache_memory:
            await app.state.registry_cache_memory.close()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
