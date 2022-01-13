""" resource manager subsystem's configuration

    - config-file schema
    - settings
"""

from aiohttp.web import Application
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY

from ._schema import CONFIG_SECTION_NAME

APP_CLIENT_REDIS_CLIENT_KEY = __name__ + ".resource_manager.redis_client"
APP_CLIENT_REDIS_LOCK_MANAGER_KEY = __name__ + ".resource_manager.redis_lock"
APP_CLIENT_REDIS_LOCK_MANAGER_CLIENT_KEY = (
    __name__ + ".resource_manager.redis_lock_client"
)
APP_CLIENT_SOCKET_REGISTRY_KEY = __name__ + ".resource_manager.registry"
APP_RESOURCE_MANAGER_TASKS_KEY = __name__ + ".resource_manager.tasks.key"


# lock names and format strings
GUEST_USER_RC_LOCK_FORMAT = f"{__name__}:redlock:garbage_collect_user:{{user_id}}"


def get_service_deletion_timeout(app: Application) -> int:
    timeout = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME][
        "resource_deletion_timeout_seconds"
    ]
    # NOTE: timeout is INT not FLOAT (timeout in expire arg at aioredis)
    return int(timeout)


def get_garbage_collector_interval(app: Application) -> int:
    return app[APP_CONFIG_KEY][CONFIG_SECTION_NAME][
        "garbage_collection_interval_seconds"
    ]
