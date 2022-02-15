""" resource manager subsystem

    Takes care of managing user generated resources such as:

    - interactive services
        - generated data

"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from ..redis import setup_redis
from .config import APP_CLIENT_SOCKET_REGISTRY_KEY, APP_RESOURCE_MANAGER_TASKS_KEY
from .registry import RedisResourceRegistry

logger = logging.getLogger(__name__)


@app_module_setup(
    "simcore_service_webserver.resource_manager", ModuleCategory.SYSTEM, logger=logger
)
def setup_resource_manager(app: web.Application) -> bool:
    """Sets up resource manager subsystem in the application"""

    app[APP_RESOURCE_MANAGER_TASKS_KEY] = []

    setup_redis(app)
    app[APP_CLIENT_SOCKET_REGISTRY_KEY] = RedisResourceRegistry(app)

    return True
