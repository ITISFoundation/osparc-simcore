"""
Lua scripts for distributed semaphore operations.

This module loads and manages Redis Lua scripts for atomic semaphore operations.
The scripts are stored in individual .lua files in the lua/ subfolder.
"""

import pathlib
from typing import Final

# Path to the lua scripts directory
_LUA_DIR = pathlib.Path(__file__).parent / "lua"


def _load_script(script_name: str) -> str:
    """Load a Lua script from the lua/ directory."""
    script_file = _LUA_DIR / f"{script_name}.lua"
    if not script_file.exists():
        msg = f"Lua script file not found: {script_file}"
        raise FileNotFoundError(msg)
    return script_file.read_text(encoding="utf-8").strip()


# Load individual scripts
ACQUIRE_SEMAPHORE_SCRIPT: Final[str] = _load_script("acquire_semaphore")
RELEASE_SEMAPHORE_SCRIPT: Final[str] = _load_script("release_semaphore")
RENEW_SEMAPHORE_SCRIPT: Final[str] = _load_script("renew_semaphore")
COUNT_SEMAPHORE_SCRIPT: Final[str] = _load_script("count_semaphore")

__all__ = [
    "ACQUIRE_SEMAPHORE_SCRIPT",
    "COUNT_SEMAPHORE_SCRIPT",
    "RELEASE_SEMAPHORE_SCRIPT",
    "RENEW_SEMAPHORE_SCRIPT",
]
