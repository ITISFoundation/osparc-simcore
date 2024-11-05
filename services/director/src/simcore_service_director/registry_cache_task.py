import asyncio
import logging

from fastapi import FastAPI
from servicelib.logging_utils import log_context
from servicelib.utils import limited_gather

from . import exceptions, registry_proxy
from .core.settings import ApplicationSettings, get_application_settings

_logger = logging.getLogger(__name__)

TASK_NAME: str = __name__ + "_registry_caching_task"


async def registry_caching_task(app: FastAPI) -> None:
    app_settings = get_application_settings(app)
    try:
        with log_context(_logger, logging.INFO, msg=f"{TASK_NAME}: starting"):
            assert hasattr(app.state, "registry_cache")  # nosec
            assert isinstance(app.state.registry_cache, dict)  # nosec
            app.state.registry_cache.clear()

        await registry_proxy.list_services(app, registry_proxy.ServiceType.ALL)
        while True:
            _logger.info("%s: waking up, refreshing cache...", TASK_NAME)
            try:
                refresh_tasks = [
                    registry_proxy.registry_request(app, key.split(":"), no_cache=True)
                    for key in app.state.registry_cache
                ]
                keys = list(app.state.registry_cache.keys())
                results = await limited_gather(*refresh_tasks, log=_logger, limit=50)

                for key, result in zip(keys, results, strict=False):
                    app.state.registry_cache[key] = result

            except exceptions.DirectorException:
                # if the registry is temporarily not available this might happen
                _logger.exception(
                    "%s: exception while refreshing cache, clean cache...", TASK_NAME
                )
                app.state.registry_cache.clear()

            _logger.info(
                "cache refreshed %s: sleeping for %ss...",
                TASK_NAME,
                app_settings.DIRECTOR_REGISTRY_CACHING_TTL,
            )
            await asyncio.sleep(
                app_settings.DIRECTOR_REGISTRY_CACHING_TTL.total_seconds()
            )
    except asyncio.CancelledError:
        _logger.info("%s: cancelling task...", TASK_NAME)
    except Exception:  # pylint: disable=broad-except
        _logger.exception("%s: Unhandled exception while refreshing cache", TASK_NAME)
    finally:
        _logger.info("%s: finished task...clearing cache...", TASK_NAME)
        app.state.registry_cache.clear()


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        app.state.registry_cache = {}
        app.state.registry_cache_task = None
        app_settings: ApplicationSettings = app.state.settings
        if not app_settings.DIRECTOR_REGISTRY_CACHING:
            _logger.info("Registry caching disabled")
            return

        app.state.registry_cache_task = asyncio.get_event_loop().create_task(
            registry_caching_task(app)
        )

    async def on_shutdown() -> None:
        if app.state.registry_cache_task:
            app.state.registry_cache_task.cancel()
            await app.state.registry_cache_task

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


__all__ = ["setup"]
