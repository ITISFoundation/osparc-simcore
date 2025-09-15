from importlib import resources
from typing import Final


def _load_script(script_name: str) -> str:
    with resources.path("servicelib", f"redis.lua.{script_name}ga") as script_file:
        return script_file.read_text(encoding="utf-8").strip()


ACQUIRE_SEMAPHORE_SCRIPT: Final[str] = _load_script("acquire_semaphore")
RELEASE_SEMAPHORE_SCRIPT: Final[str] = _load_script("release_semaphore")
RENEW_SEMAPHORE_SCRIPT: Final[str] = _load_script("renew_semaphore")
COUNT_SEMAPHORE_SCRIPT: Final[str] = _load_script("count_semaphore")
