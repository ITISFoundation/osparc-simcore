APP_CLIENT_REDIS_CLIENT_KEY = __name__ + ".resource_manager.redis_client"
APP_CLIENT_REDIS_LOCK_MANAGER_KEY = __name__ + ".resource_manager.redis_lock"
APP_CLIENT_REDIS_LOCK_MANAGER_CLIENT_KEY = (
    __name__ + ".resource_manager.redis_lock_client"
)
APP_CLIENT_SOCKET_REGISTRY_KEY = __name__ + ".resource_manager.registry"
APP_RESOURCE_MANAGER_TASKS_KEY = __name__ + ".resource_manager.tasks.key"

# lock names and format strings
GUEST_USER_RC_LOCK_FORMAT = f"{__name__}:redlock:garbage_collect_user:{{user_id}}"
