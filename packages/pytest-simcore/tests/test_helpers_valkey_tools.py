"""Pins `flush_databases` to clearing one logical database per client.

The xdist workers share one valkey server and each client is pinned to a database of its bank, so
a `flushall` here would wipe the other workers' data (e.g. the semaphore tokens their tasks wait
for) while every test of this worker still passes.
"""

from typing import TYPE_CHECKING, cast

from pytest_simcore.helpers.valkey_tools import flush_databases

if TYPE_CHECKING:
    # annotation only, as in `valkey_tools`: this package must stay loadable without redis
    from redis.asyncio import Redis


class _RecordingClient:
    """Stands in for a client and records which flush command the code under test issues.

    `mock.create_autospec(Redis)` would check the real signature, but this package must stay
    loadable without the redis dependency, which is why `valkey_tools` imports it for annotations
    only.
    """

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def flushdb(self) -> None:
        self.calls.append("flushdb")

    async def flushall(self) -> None:
        self.calls.append("flushall")


async def test_flush_databases_clears_each_client_database_and_nothing_else():
    client_a = _RecordingClient()
    client_b = _RecordingClient()

    # the double only ever answers `flushdb`, which is all the code under test calls
    await flush_databases(cast("Redis", client_a), cast("Redis", client_b))

    assert client_a.calls == ["flushdb"]
    assert client_b.calls == ["flushdb"]


async def test_flush_databases_without_clients_is_a_no_op():
    await flush_databases()
