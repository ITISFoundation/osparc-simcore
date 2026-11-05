"""TCP ports for a whole pytest session, safe to use from several pytest-xdist workers.

Load it with ``pytest_plugins = ["pytest_simcore.xdist_unused_tcp_ports"]`` in a suite that starts
servers on ``unused_tcp_port``/``unused_tcp_port_factory`` and runs under xdist. It replaces the two
fixtures with those names from pytest-asyncio, whose ``unused_tcp_port_factory`` remembers only the
ports handed to its own process and whose ``unused_tcp_port`` remembers none at all: two workers can
be given the same port and the last one to bind it errors with ``Address already in use``. See
`helpers.xdist_ports` for how the ports are split between workers.
"""

from collections.abc import Callable
from pathlib import Path

import pytest

from .helpers.stack_names import get_checkout_uid
from .helpers.xdist import get_worker_id, get_xdist_worker_count
from .helpers.xdist_ports import get_port_allocator


@pytest.fixture(scope="session")
def unused_tcp_port_factory(request: pytest.FixtureRequest, osparc_simcore_root_dir: Path) -> Callable[[], int]:
    allocator = get_port_allocator(
        worker_id=get_worker_id(request),
        worker_count=get_xdist_worker_count(request),
        checkout_uid=get_checkout_uid(osparc_simcore_root_dir),
    )
    return allocator.get


@pytest.fixture
def unused_tcp_port(unused_tcp_port_factory: Callable[[], int]) -> int:
    # pytest-asyncio's fixture with this name draws a port on its own, without the factory's book
    return unused_tcp_port_factory()
