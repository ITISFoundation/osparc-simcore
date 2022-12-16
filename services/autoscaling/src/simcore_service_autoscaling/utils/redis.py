import functools

from servicelib.redis import RedisClientSDK


def locked_task(redis: RedisClientSDK):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # lock_key = f"{app.title}:dynamic_services_resources:node_labels:{app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS}"
            async with redis.lock_context(lock_key="test"):
                return await func(*args, **kwargs)

        return wrapper

    return decorator
