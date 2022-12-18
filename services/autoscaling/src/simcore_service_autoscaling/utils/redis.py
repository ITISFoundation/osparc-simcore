import functools

from servicelib.redis import RedisClientSDK


def exclusive(redis: RedisClientSDK, *, lock_key: str):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            async with redis.lock_context(lock_key=lock_key):
                return await func(*args, **kwargs)

        return wrapper

    return decorator
