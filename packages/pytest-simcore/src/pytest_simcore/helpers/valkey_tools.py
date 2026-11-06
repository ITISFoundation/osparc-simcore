"""Helpers for the valkey/redis server shared by the xdist workers.

The workers share one server, so their data must stay inside the bank of logical databases
reserved for them:
- ``--databases`` can only be set when the server starts (it is NOT ``CONFIG SET``-able), so the
  number of logical databases must be fixed in the compose file BEFORE the stack is deployed. The
  deployed ``services/docker-compose.yml`` keeps a small default; under pytest-xdist the test
  fixtures widen it in the *generated* union compose (never the deployed one) to reserve one bank
  of logical databases per worker, so concurrent workers never collide on the same DB indices.
- clearing data must therefore use ``flushdb`` on a client of that bank, see `flush_databases`.
"""

from typing import Final

from redis.asyncio import Redis

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


async def flush_databases(*clients: Redis) -> None:
    """Clears the database each client is connected to.

    Each client is pinned to one logical database (see `RedisSettings.build_redis_dsn`), so this
    clears exactly the databases of the caller's bank. `flushall` is never used here: it clears
    every database of the shared server, i.e. the data of the other xdist workers too, which then
    lose e.g. the semaphore tokens their tasks are waiting for.
    """
    for client in clients:
        await client.flushdb()
