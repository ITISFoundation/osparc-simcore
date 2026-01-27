"""used to load a lua script from the package resources in memory

Example:
    >>> from servicelib.redis._semaphore_lua import ACQUIRE_SEMAPHORE_SCRIPT
    # This will register the script in redis and return a Script object
    # which can be used to execute the script. Even from multiple processes
    # the script will be loaded only once in redis as the redis server computes
    # the SHA1 of the script and uses it to identify it.
    >>> from aioredis import Redis
    >>> redis = Redis(...)
    >>> my_acquire_script = redis.register_script(
        ACQUIRE_SEMAPHORE_SCRIPT
    >>> my_acquire_script(keys=[...], args=[...])
"""

from typing import Final

from ..utils import load_script

# fair semaphore scripts (token pool based)
REGISTER_SEMAPHORE_TOKEN_SCRIPT: Final[str] = load_script("servicelib.redis.lua", "register_semaphore_tokens")
ACQUIRE_SEMAPHORE_SCRIPT: Final[str] = load_script("servicelib.redis.lua", "acquire_semaphore")
RELEASE_SEMAPHORE_SCRIPT: Final[str] = load_script("servicelib.redis.lua", "release_semaphore")
RENEW_SEMAPHORE_SCRIPT: Final[str] = load_script("servicelib.redis.lua", "renew_semaphore")


SCRIPT_OK_EXIT_CODE: Final[int] = 0
SCRIPT_BAD_EXIT_CODE: Final[int] = 255
