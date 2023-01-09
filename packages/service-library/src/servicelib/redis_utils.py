import functools
import logging
from typing import Optional, Union

from .redis import RedisClientSDK

log = logging.getLogger(__file__)


def exclusive(
    redis: RedisClientSDK,
    *,
    lock_key: str,
    lock_value: Optional[Union[bytes, str]] = None
):
    """
    Define a method to run exclusively accross
    processes by leveraging a Redis Lock.

    parameters:
    redis: the redis client SDK
    lock_key: a string as the name of the lock (good practice: app_name:lock_name)
    lock_value: some additional data that can be retrieved by another client
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            async with redis.lock_context(lock_key=lock_key, lock_value=lock_value):
                return await func(*args, **kwargs)

        return wrapper

    return decorator
