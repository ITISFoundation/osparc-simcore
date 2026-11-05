"""TCP ports for the servers tests bind, sliced so that pytest-xdist workers cannot get the same one.

pytest-asyncio's ``unused_tcp_port_factory`` learns a free port by binding port 0 and releasing it, and
remembers only the ports handed to its own process. Two xdist workers can
therefore receive the same port, and the one that binds it last fails with ``Address already in
use``. Two properties remove the race here: ports are drawn from a range the kernel does not allocate
on its own, so no unrelated socket takes a port between the hand-out and the bind, and every worker of
a run draws from a slice that no other worker of the run (or of another checkout) uses.
"""

import random
import socket
from typing import Annotated, Final

from annotated_types import doc

from .xdist import WORKER_ID_MASTER

FIRST_TEST_PORT: Final[
    Annotated[
        int,
        doc(
            "first port a test server binds, below the kernel's ephemeral range (32768-60999 on Linux)"
            " and below what docker swarm publishes service ports from (30000-32767)"
        ),
    ]
] = 20000

_PORTS_PER_CHECKOUT: Final[Annotated[int, doc("ports one checkout owns, split over the workers of its run")]] = 4000

_CHECKOUT_SLOTS: Final[Annotated[int, doc("port ranges that co-tenant checkouts alternate between")]] = 2


class NoFreeTCPPortError(RuntimeError):
    """Every port of a worker's slice is either bound or was already handed out"""


def is_port_free(port: int) -> bool:
    """True when nothing binds `port` right now (with SO_REUSEADDR, as the test servers do)"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
        return True


class TcpPortAllocator:
    """Hands out ports of a slice, each of them at most once and only while nothing binds it"""

    def __init__(self, ports: range) -> None:
        self._ports = ports
        self._handed_out: set[int] = set()
        self._random = random.Random()  # noqa: S311

    @property
    def ports(self) -> range:
        return self._ports

    def get(self) -> int:
        # shuffled so that co-tenant workers do not all fill their slice from the same end
        for port in self._random.sample(self._ports, k=len(self._ports)):
            if port in self._handed_out or not is_port_free(port):
                continue
            self._handed_out.add(port)
            return port

        handed_out = len(self._handed_out)
        msg = f"no free TCP port left in {self._ports.start}-{self._ports.stop} ({handed_out} already handed out)"
        raise NoFreeTCPPortError(msg)


def get_port_allocator(*, worker_id: str, max_workers: int, checkout_uid: str) -> TcpPortAllocator:
    """Slice of ports reserved for `worker_id`, disjoint from the other workers of the run and from
    the workers of any other checkout sharing the same network namespace

    NOTE: `max_workers` (see `helpers.xdist.get_max_xdist_workers`) bounds the number of workers, so
    a slice cannot run past its checkout's range when xdist spawns fewer of them.
    """
    checkout_slot = int(checkout_uid, 16) % _CHECKOUT_SLOTS
    max_workers = max(max_workers, 1)
    ports_per_worker = _PORTS_PER_CHECKOUT // max_workers
    worker_index = _get_worker_index(worker_id)
    assert worker_index < max_workers
    first = FIRST_TEST_PORT + checkout_slot * _PORTS_PER_CHECKOUT + worker_index * ports_per_worker
    return TcpPortAllocator(range(first, first + ports_per_worker))


def _get_worker_index(worker_id: str) -> int:
    """Index of an xdist worker (``gw2`` is 2), 0 for the controller and for non-xdist runs"""
    if worker_id.startswith("gw"):
        return int(worker_id.removeprefix("gw"))
    assert worker_id == WORKER_ID_MASTER
    return 0
