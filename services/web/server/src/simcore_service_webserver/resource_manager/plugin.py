"""resource manager subsystem

Takes care of managing user generated resources such as:

- interactive services
    - generated data

"""

import logging

from aiohttp import web

from ..application_setup import ModuleCategory, app_setup_func
from ..redis import setup_redis
from .registry import CLIENT_SOCKET_REGISTRY_APPKEY, RedisResourceRegistry

_logger = logging.getLogger(__name__)


@app_setup_func(
    "simcore_service_webserver.resource_manager",
    ModuleCategory.SYSTEM,
    settings_name="WEBSERVER_RESOURCE_MANAGER",
    logger=_logger,
)
def setup_resource_manager(app: web.Application) -> bool:
    """Sets up resource manager subsystem in the application"""

    setup_redis(app)
    app[CLIENT_SOCKET_REGISTRY_APPKEY] = RedisResourceRegistry(app)

    return True
