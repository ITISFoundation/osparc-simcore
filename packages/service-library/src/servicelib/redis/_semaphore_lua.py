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

from functools import lru_cache
from importlib import resources
from typing import Final


@lru_cache
def _load_script(script_name: str) -> str:
    with resources.as_file(
        resources.files("servicelib.redis.lua") / f"{script_name}.lua"
    ) as script_file:
        return script_file.read_text(encoding="utf-8").strip()


# fair semaphore scripts (token pool based)
REGISTER_SEMAPHORE_TOKEN_SCRIPT: Final[str] = _load_script("register_semaphore_tokens")
ACQUIRE_SEMAPHORE_SCRIPT: Final[str] = _load_script("acquire_semaphore")
RELEASE_SEMAPHORE_SCRIPT: Final[str] = _load_script("release_semaphore")
RENEW_SEMAPHORE_SCRIPT: Final[str] = _load_script("renew_semaphore")


SCRIPT_OK_EXIT_CODE: Final[int] = 0
SCRIPT_BAD_EXIT_CODE: Final[int] = 255
