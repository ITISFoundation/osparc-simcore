""" resource manager subsystem's configuration

    - config-file schema
    - settings
"""
import trafaret as T
from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY

CONFIG_SECTION_NAME = 'resource_manager'
APP_RESOURCE_MANAGER_TASKS_KEY = __name__ + ".resource_manager.tasks.key"

schema = T.Dict({
    T.Key("enabled", default=True, optional=True): T.Or(T.Bool(), T.Int()),
    T.Key("service_deletion_timeout_seconds", default=900, optional=True): T.Int(),
})


def get_service_deletion_timeout(app: web.Application) -> int:
    return app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]["service_deletion_timeout_seconds"]
