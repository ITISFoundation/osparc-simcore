"""TCP ports for a whole pytest session, safe to use from several pytest-xdist workers.

Load it with ``pytest_plugins = ["pytest_simcore.xdist_unused_tcp_ports"]`` in a suite that starts
servers on ``unused_tcp_port``/``unused_tcp_port_factory`` and runs under xdist. It replaces the two
fixtures with those names from pytest-asyncio, whose ``unused_tcp_port_factory`` remembers only the
ports handed to its own process and whose ``unused_tcp_port`` remembers none at all: two workers can
be given the same port and the last one to bind it errors with ``Address already in use``. See
`helpers.xdist_ports` for how a port is reserved for the process that got it.
"""

from collections.abc import Callable

import pytest

from .helpers.xdist_ports import get_port_allocator


@pytest.fixture(scope="session")
def unused_tcp_port_factory() -> Callable[[], int]:
    return get_port_allocator().get


@pytest.fixture
def unused_tcp_port(unused_tcp_port_factory: Callable[[], int]) -> int:
    # pytest-asyncio's fixture with this name draws a port on its own, without the factory's book
    return unused_tcp_port_factory()
