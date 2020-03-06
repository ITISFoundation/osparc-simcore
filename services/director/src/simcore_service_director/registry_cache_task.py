import asyncio
import logging

from aiohttp import web

from simcore_service_director import config, exceptions, registry_proxy
from simcore_service_director.config import APP_REGISTRY_CACHE_DATA_KEY

_logger = logging.getLogger(__name__)

TASK_NAME: str = __name__ + "_registry_caching_task"
async def registry_caching_task(app: web.Application) -> None:
    try:
        _logger.info("%s: initializing...", TASK_NAME)
        app[APP_REGISTRY_CACHE_DATA_KEY].clear()
        _logger.info("%s: initialisation completed", TASK_NAME)
        while True:
            _logger.info("%s: waking up, cleaning registry cache...", TASK_NAME)
            app[APP_REGISTRY_CACHE_DATA_KEY].clear()
            _logger.info("%s: caching services list...", TASK_NAME)
            try:
                await registry_proxy.list_services(app, registry_proxy.ServiceType.ALL)
            except exceptions.DirectorException:
                # if the registry is temporarily not available this might happen
                app[APP_REGISTRY_CACHE_DATA_KEY].clear()

            _logger.info("%s: sleeping for %ss...", TASK_NAME, config.DIRECTOR_REGISTRY_CACHING_TTL)
            await asyncio.sleep(config.DIRECTOR_REGISTRY_CACHING_TTL)
    except asyncio.CancelledError:
        _logger.info("%s: cancelling task...", TASK_NAME)
    except Exception: #pylint: disable=broad-except
        _logger.exception("%s: exception while retrieving list of services in cache", TASK_NAME)
    finally:
        _logger.info("%s: finished task...clearing cache...", TASK_NAME)
        app[APP_REGISTRY_CACHE_DATA_KEY].clear()

async def setup_registry_caching_task(app: web.Application) -> None:
    app[APP_REGISTRY_CACHE_DATA_KEY] = {}
    app[TASK_NAME] = asyncio.get_event_loop().create_task(registry_caching_task(app))

    yield

    task = app[TASK_NAME]
    task.cancel()
    await task

def setup(app: web.Application) -> None:
    if config.DIRECTOR_REGISTRY_CACHING:
        app.cleanup_ctx.append(setup_registry_caching_task)
        


__all__ = [
    "setup",
    "APP_REGISTRY_CACHE_DATA_KEY"
]
