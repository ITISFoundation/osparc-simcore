"""Pins `flush_databases` to clearing one logical database per client.

The xdist workers share one valkey server and each client is pinned to a database of its bank, so
a `flushall` here would wipe the other workers' data (e.g. the semaphore tokens their tasks wait
for) while every test of this worker still passes.
"""

from pytest_simcore.helpers.valkey_tools import flush_databases


class _RecordingClient:
    # `mock.create_autospec(Redis)` would check the real signature, but this package must stay
    # loadable without the redis dependency, which is why `valkey_tools` imports it for
    # annotations only
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def flushdb(self) -> None:
        self.calls.append("flushdb")

    async def flushall(self) -> None:
        self.calls.append("flushall")


async def test_flush_databases_clears_each_client_database_and_nothing_else():
    client_a = _RecordingClient()
    client_b = _RecordingClient()

    await flush_databases(client_a, client_b)

    assert client_a.calls == ["flushdb"]
    assert client_b.calls == ["flushdb"]


async def test_flush_databases_without_clients_is_a_no_op():
    await flush_databases()
