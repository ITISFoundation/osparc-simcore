""" resource manager subsystem

    Takes care of managing user generated resources such as:

    - interactive services
        - generated data

"""
import logging

from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.application_setup import ModuleCategory, app_module_setup

from .config import (APP_CLIENT_SOCKET_REGISTRY_KEY,
                     APP_RESOURCE_MANAGER_TASKS_KEY, CONFIG_SECTION_NAME)
from .garbage_collector import setup as setup_garbage_collector
from .redis import setup_redis_client
from .registry import RedisResourceRegistry

logger = logging.getLogger(__name__)

MODULE_NAME = __name__.split(".")[-1]
module_name = module_name = __name__.replace(".__init__", "")

@app_module_setup(module_name, ModuleCategory.SYSTEM, logger=logger)
def setup(app: web.Application) -> bool:
    """Sets up resource manager subsystem in the application

    """
    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
    app[APP_RESOURCE_MANAGER_TASKS_KEY] = []
    setup_redis_client(app)
    app[APP_CLIENT_SOCKET_REGISTRY_KEY] = RedisResourceRegistry(app) if cfg["redis"]["enabled"] \
                                    else None
    setup_garbage_collector(app)
    return True


# alias
setup_resource_manager = setup

__all__ = (
    'setup_resource_manager'
)
