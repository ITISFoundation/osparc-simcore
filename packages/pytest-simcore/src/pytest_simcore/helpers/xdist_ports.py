"""TCP ports for the servers tests bind, reserved so that no two pytest processes get the same one.

pytest-asyncio's ``unused_tcp_port_factory`` learns a free port by binding port 0 and releasing it, and
remembers only the ports handed to its own process; its ``unused_tcp_port`` remembers none at all. Two
xdist workers, or two checkouts running on one host, can therefore receive the same port, and the one that
binds it last fails with ``Address already in use``. Two properties remove the race here:

- ports are drawn from a band the kernel does not allocate on its own, so no unrelated socket takes a port
  between the hand-out and the bind, and
- every port a process hands out goes into a reservation file together with its PID, and a process skips
  the ports a live process reserved. Entries of dead processes are dropped when the file is next read, so a
  crashed worker releases what it held.

The reservation file, not a split of the band, is what makes the ports exclusive. xdist hands worker ids
out from an execnet counter that never restarts, and a worker that crashes comes back with an id above the
worker count of the run, so no division of a band by a count or an id covers them all.
"""

import os
import random
import socket
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import Annotated, Final

from annotated_types import doc
from common_library.json_serialization import json_dumps, json_loads
from filelock import FileLock

FIRST_TEST_PORT: Final[
    Annotated[
        int,
        doc(
            "first port a test server binds, below the kernel's ephemeral range (32768-60999 on Linux)"
            " and below what docker swarm publishes service ports from (30000-32767)"
        ),
    ]
] = 20000

_NUMBER_OF_TEST_PORTS: Final[
    Annotated[int, doc("ports above FIRST_TEST_PORT a test server may bind, i.e. how far the band reaches")]
] = 8000

_RESERVATIONS_FILE_NAME: Final[
    Annotated[str, doc("file of the host's temp dir recording which test port belongs to which pytest process")]
] = "osparc-simcore-test-tcp-ports.json"

_LOCK_TIMEOUT: Final[
    Annotated[
        timedelta,
        doc("wait for the reservation file, which another process holds only while it picks a single port"),
    ]
] = timedelta(seconds=30)


class NoFreeTCPPortError(RuntimeError):
    """Every port of the band is either bound or reserved by a live process"""


def is_port_free(port: int) -> bool:
    """True when nothing binds `port` right now (with SO_REUSEADDR, as the test servers do)"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
        return True


def _pid_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # another user's process, but alive
    return True


@contextmanager
def _ports_of_live_processes(*, lock_path: Path, reservations_path: Path) -> Iterator[dict[int, int]]:
    """Yields the ports live pytest processes hold, and writes them back on the way out"""
    with FileLock(lock_path, timeout=_LOCK_TIMEOUT.total_seconds()):
        held = _load_reservations(reservations_path)
        alive = {port: pid for port, pid in held.items() if _pid_is_alive(pid)}
        yield alive
        _dump_reservations(reservations_path, alive)


class TcpPortAllocator:
    """Hands out ports of the band, each of them to one live pytest process at a time

    A port stays reserved for the lifetime of the process it went to, so no run hands one out twice, and a
    process that dies releases what it held as soon as another one reads the file.
    """

    def __init__(self, *, ports: range, reservations_path: Path) -> None:
        self._ports = ports
        self._reservations_path = reservations_path
        self._lock_path = reservations_path.with_name(f"{reservations_path.name}.lock")
        # shuffled so that co-tenant processes do not all fill the band from the same end
        self._candidates = tuple(random.Random().sample(ports, k=len(ports)))  # noqa: S311

        with _ports_of_live_processes(lock_path=self._lock_path, reservations_path=self._reservations_path) as held:
            # the OS reuses PIDs: what an earlier process with this one reserved is not ours to keep
            for port, pid in tuple(held.items()):
                if pid == os.getpid():
                    del held[port]

    @property
    def ports(self) -> range:
        return self._ports

    @property
    def reservations_path(self) -> Path:
        return self._reservations_path

    def get(self) -> int:
        with _ports_of_live_processes(lock_path=self._lock_path, reservations_path=self._reservations_path) as held:
            for port in self._candidates:
                if port in held or not is_port_free(port):
                    continue
                held[port] = os.getpid()
                return port

        msg = f"no free TCP port left in {self._ports.start}-{self._ports.stop - 1} ({len(held)} reserved)"
        raise NoFreeTCPPortError(msg)


def _load_reservations(reservations_path: Path) -> dict[int, int]:
    if not reservations_path.is_file():
        return {}
    try:
        return {int(port): pid for port, pid in json_loads(reservations_path.read_text()).items()}
    except AttributeError, OSError, TypeError, ValueError:
        # another process wrote a shape this one does not understand, or wrote it halfway
        return {}


def _dump_reservations(reservations_path: Path, reservations: dict[int, int]) -> None:
    # JSON object keys are strings, so a reader from another pytest version can still parse the file
    reservations_path.write_text(json_dumps({str(port): pid for port, pid in reservations.items()}))


def get_port_allocator(*, reservations_path: Path | None = None) -> TcpPortAllocator:
    """Allocator over the whole test port band of the host's temp dir

    `reservations_path` defaults to the file every pytest process sharing that temp dir coordinates
    through. Pass another one to keep a run to its own ports, e.g. in a test.
    """
    return TcpPortAllocator(
        ports=range(FIRST_TEST_PORT, FIRST_TEST_PORT + _NUMBER_OF_TEST_PORTS),
        reservations_path=reservations_path or Path(tempfile.gettempdir()) / _RESERVATIONS_FILE_NAME,
    )
