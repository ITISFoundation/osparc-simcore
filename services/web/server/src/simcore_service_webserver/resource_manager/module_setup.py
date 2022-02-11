""" resource manager subsystem

    Takes care of managing user generated resources such as:

    - interactive services
        - generated data

"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from .config import APP_CLIENT_SOCKET_REGISTRY_KEY, APP_RESOURCE_MANAGER_TASKS_KEY
from .garbage_collector import setup_garbage_collector
from .redis import setup_redis_client
from .registry import RedisResourceRegistry

logger = logging.getLogger(__name__)


@app_module_setup(
    "simcore_service_webserver.resource_manager", ModuleCategory.ADDON, logger=logger
)
def setup_resource_manager(app: web.Application) -> bool:
    """Sets up resource manager subsystem in the application"""

    # ----------------------------------------------
    # TODO: temporary, just to check compatibility between
    # trafaret and pydantic schemas
    # assert_valid_config(app)
    # ---------------------------------------------

    app[APP_RESOURCE_MANAGER_TASKS_KEY] = []
    setup_redis_client(app)
    app[APP_CLIENT_SOCKET_REGISTRY_KEY] = RedisResourceRegistry(app)
    setup_garbage_collector(app)
    return True
