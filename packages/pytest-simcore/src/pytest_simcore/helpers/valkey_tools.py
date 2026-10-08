"""Helpers to read/widen the valkey/redis ``--databases`` boot-time argument in a compose dict.

``--databases`` can only be set when the server starts (it is NOT ``CONFIG SET``-able), so the
number of logical databases must be fixed in the compose file BEFORE the stack is deployed. The
deployed ``services/docker-compose.yml`` keeps a small default; under pytest-xdist the test
fixtures widen it in the *generated* union compose (never the deployed one) to reserve one bank
of logical databases per worker, so concurrent workers never collide on the same DB indices.
"""

from typing import Final

_VALKEY_DATABASES_FLAG: Final[str] = "--databases"


def get_valkey_databases_count(compose_dict: dict) -> int | None:
    """Returns the value passed after ``--databases`` in the ``redis`` service command, or None."""
    command = compose_dict.get("services", {}).get("redis", {}).get("command")
    if not isinstance(command, list):
        return None
    for index, token in enumerate(command):
        if token == _VALKEY_DATABASES_FLAG and index + 1 < len(command):
            return int(command[index + 1])
    return None


def set_valkey_databases_count(compose_dict: dict, count: int) -> None:
    """Sets the value passed after ``--databases`` in the ``redis`` service command (in place)."""
    command = compose_dict["services"]["redis"]["command"]
    index = command.index(_VALKEY_DATABASES_FLAG)
    command[index + 1] = str(count)
