""" resource manager subsystem

    Takes care of managing user generated resources such as:

    - interactive services
        - generated data

"""
import logging

from aiohttp import web
from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.application_setup import ModuleCategory, app_module_setup

from .config import (
    APP_CLIENT_SOCKET_REGISTRY_KEY,
    APP_RESOURCE_MANAGER_TASKS_KEY,
    CONFIG_SECTION_NAME,
    ResourceManagerSettings,
)
from .garbage_collector import setup_garbage_collector
from .redis import setup_redis_client
from .registry import RedisResourceRegistry

logger = logging.getLogger(__name__)


@app_module_setup(__name__, ModuleCategory.SYSTEM, logger=logger)
def setup_resource_manager(app: web.Application, **cfg_settings) -> bool:
    """Sets up resource manager subsystem in the application"""
    cfg = ResourceManagerSettings(**cfg_settings)
    app[APP_CONFIG_KEY][CONFIG_SECTION_NAME] = cfg

    app[APP_RESOURCE_MANAGER_TASKS_KEY] = []
    setup_redis_client(app)
    app[APP_CLIENT_SOCKET_REGISTRY_KEY] = RedisResourceRegistry(app)
    setup_garbage_collector(app)
    return True
