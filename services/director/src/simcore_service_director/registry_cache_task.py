import asyncio
import logging
from enum import IntEnum

from aiohttp import web

from simcore_service_director import config, registry_proxy
from simcore_service_director.config import APP_REGISTRY_CACHE_DATA_KEY

_logger = logging.getLogger(__name__)

TASK_NAME: str = __name__ + "_registry_caching_task"
TASK_STATE: str = "{}_state".format(TASK_NAME)

class State(IntEnum):
    STARTING = 0
    RUNNING = 1
    FAILED = 2
    STOPPED = 3

async def registry_caching_task(app: web.Application) -> None:
    try:
        _logger.info("initializing...")
        app[TASK_STATE] = State.STARTING
        app[APP_REGISTRY_CACHE_DATA_KEY] = {}
        _logger.info("initialisation completed")
        app[TASK_STATE] = State.RUNNING
        while True:
            app[APP_REGISTRY_CACHE_DATA_KEY].clear()
            await registry_proxy.list_services(app, registry_proxy.ServiceType.ALL)
            await asyncio.sleep(config.REGISTRY_CACHING_TTL)
    except asyncio.CancelledError:
        _logger.info("cancelling task...")
        app[TASK_STATE] = State.STOPPED
        raise
    except:
        _logger.exception("task closing:")
        app[TASK_STATE] = State.FAILED
        raise
    finally:
        _logger.info("finished task...")

async def start(app: web.Application) -> None:
    _logger.info("starting registry caching task")    
    app[TASK_NAME] = asyncio.get_event_loop().create_task(registry_caching_task(app))

async def cleanup(app: web.Application) -> None:
    task = app[TASK_NAME]
    task.cancel()

def setup(app: web.Application) -> None:
    if config.REGISTRY_CACHING:
        app.on_startup.append(start)
        app.on_cleanup.append(cleanup)



__all__ = [
    "setup",
    "State",
    "APP_REGISTRY_CACHE_DATA_KEY"
]
