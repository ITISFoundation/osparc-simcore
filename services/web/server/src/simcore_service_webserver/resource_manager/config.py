""" resource manager subsystem's configuration

    - config-file schema
    - settings
"""
import trafaret as T
from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY

CONFIG_SECTION_NAME = 'resource_manager'
APP_CLIENT_REDIS_CLIENT_KEY = __name__ + ".resource_manager.redis_client"
APP_CLIENT_SOCKET_REGISTRY_KEY = __name__ + ".resource_manager.registry"
APP_RESOURCE_MANAGER_TASKS_KEY = __name__ + ".resource_manager.tasks.key"
APP_GARBAGE_COLLECTOR_KEY = __name__ + ".resource_manager.garbage_collector_key"

schema = T.Dict({
    T.Key("enabled", default=True, optional=True): T.Or(T.Bool(), T.Int()),
    T.Key("resource_deletion_timeout_seconds", default=900, optional=True): T.Int(),
    T.Key("garbage_collection_interval_seconds", default=30, optional=True): T.Int(),
    T.Key("redis", optional=False): T.Dict({
        T.Key("enabled", default=True, optional=True): T.Bool(),
        T.Key("host", default="redis", optional=True): T.String(),
        T.Key("port", default=6793, optional=True): T.Int(),
    }),
})


def get_service_deletion_timeout(app: web.Application) -> int:
    return app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]["resource_deletion_timeout_seconds"]

def get_garbage_collector_interval(app: web.Application) -> int:
    return app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]["garbage_collection_interval_seconds"]
