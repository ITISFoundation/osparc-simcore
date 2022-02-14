""" resource manager subsystem

    Takes care of managing user generated resources such as:

    - interactive services
        - generated data

"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import (
    AlreadyInitializedError,
    ModuleCategory,
    app_module_setup,
)

from ..garbage_collector import setup_garbage_collector
from ..redis import setup_redis
from .config import APP_CLIENT_SOCKET_REGISTRY_KEY, APP_RESOURCE_MANAGER_TASKS_KEY
from .registry import RedisResourceRegistry

logger = logging.getLogger(__name__)


@app_module_setup(
    "simcore_service_webserver.resource_manager", ModuleCategory.ADDON, logger=logger
)
def setup_resource_manager(app: web.Application) -> bool:
    """Sets up resource manager subsystem in the application"""

    app[APP_RESOURCE_MANAGER_TASKS_KEY] = []
    try:
        setup_redis(app)
    except AlreadyInitializedError as err:
        logger.info("Skips setting up redis client: %s", err)

    app[APP_CLIENT_SOCKET_REGISTRY_KEY] = RedisResourceRegistry(app)

    try:
        setup_garbage_collector(app)
    except AlreadyInitializedError as err:
        logger.info("Skips setting up garbage collector task: %s", err)

    return True
