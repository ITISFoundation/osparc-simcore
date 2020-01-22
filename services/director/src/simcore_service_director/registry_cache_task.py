import asyncio
import logging

from aiohttp import web

from simcore_service_director import config, exceptions, registry_proxy
from simcore_service_director.config import APP_REGISTRY_CACHE_DATA_KEY

_logger = logging.getLogger(__name__)

TASK_NAME: str = __name__ + "_registry_caching_task"
async def registry_caching_task(app: web.Application) -> None:
    try:
        _logger.info("initializing...")
        app[APP_REGISTRY_CACHE_DATA_KEY].clear()
        _logger.info("initialisation completed")
        while True:
            app[APP_REGISTRY_CACHE_DATA_KEY].clear()
            await registry_proxy.list_services(app, registry_proxy.ServiceType.ALL)
            await asyncio.sleep(config.REGISTRY_CACHING_TTL)
    except asyncio.CancelledError:
        _logger.info("cancelling task...")        
    except exceptions.DirectorException:
        _logger.exception("exception while retrieving list of services in cache")
    finally:
        _logger.info("finished task...clearing cache...")
        app[APP_REGISTRY_CACHE_DATA_KEY].clear()

async def setup_registry_caching_task(app: web.Application) -> None:
    _logger.info("starting registry caching task")
    app[APP_REGISTRY_CACHE_DATA_KEY] = {}
    app[TASK_NAME] = asyncio.get_event_loop().create_task(registry_caching_task(app))

    yield

    task = app[TASK_NAME]
    task.cancel()
    await task

def setup(app: web.Application) -> None:
    if config.REGISTRY_CACHING:
        app.cleanup_ctx.append(setup_registry_caching_task)
        


__all__ = [
    "setup",
    "APP_REGISTRY_CACHE_DATA_KEY"
]
