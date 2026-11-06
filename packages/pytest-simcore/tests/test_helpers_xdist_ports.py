# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import contextlib
import json
import os
import socket
import subprocess
import sys
from collections.abc import Iterator, Sequence
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Annotated, Final

import pytest
from annotated_types import doc
from pytest_simcore.helpers.xdist_ports import (
    FIRST_TEST_PORT,
    NoFreeTCPPortError,
    TcpPortAllocator,
    get_port_allocator,
    is_port_free,
)

_ABOVE_THE_BAND: Final[
    Annotated[range, doc("ports just above the band, so a concurrent pytest run cannot hold these")]
] = range(FIRST_TEST_PORT + 8000, FIRST_TEST_PORT + 8010)

_DOCKER_SWARM_FIRST_PUBLISHED_PORT: Final[Annotated[int, doc("docker swarm publishes service ports from here")]] = 30000


def _free_ports(count: int) -> tuple[int, ...]:
    """Ports of the tested range that nothing holds right now"""
    free = tuple(port for port in _ABOVE_THE_BAND if is_port_free(port))
    if len(free) < count:
        pytest.skip(f"{count} free ports needed in {list(_ABOVE_THE_BAND)}, {len(free)} found")
    return free[:count]


@contextmanager
def _only_these_are_selectable(selectable: Sequence[int]) -> Iterator[None]:
    """Holds every port of the tested range but `selectable`, so those are the only ones the allocator can pick"""
    with ExitStack() as stack:
        for port in _ABOVE_THE_BAND:
            if port in selectable:
                continue
            sock = stack.enter_context(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
            with contextlib.suppress(OSError):
                # a port somebody else holds is held, which is all this helper is after
                sock.bind(("127.0.0.1", port))
        yield


def _allocator(reservations_path: Path) -> TcpPortAllocator:
    return TcpPortAllocator(ports=_ABOVE_THE_BAND, reservations_path=reservations_path)


def _reserved_by(reservations_path: Path, port: int, pid: int) -> None:
    """Writes a reservation the way `pid` left it behind"""
    reservations_path.write_text(json.dumps({str(port): pid}))


def _a_finished_pid() -> int:
    """A PID that runs nothing anymore"""
    with subprocess.Popen([sys.executable, "-c", "pass"]) as proc:
        proc.wait()
        return proc.pid


def test_port_is_free_only_when_nothing_holds_it():
    (port,) = _free_ports(1)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", port))
        assert is_port_free(port) is False

    assert is_port_free(port) is True


def test_allocator_hands_out_a_port_nothing_holds(tmp_path: Path):
    selectable = _free_ports(2)
    with _only_these_are_selectable(selectable):
        port = _allocator(tmp_path / "ports.json").get()

    assert port in selectable


def test_allocator_skips_a_port_a_live_process_reserved(tmp_path: Path):
    reservations = tmp_path / "ports.json"
    (port,) = _free_ports(1)
    _reserved_by(reservations, port, os.getppid())

    with _only_these_are_selectable((port,)):
        with pytest.raises(NoFreeTCPPortError):
            _allocator(reservations).get()
        # only the reservation kept it out of the run
        assert _allocator(tmp_path / "nothing-else.json").get() == port


def test_allocator_reclaims_a_port_a_dead_process_reserved(tmp_path: Path):
    reservations = tmp_path / "ports.json"
    (port,) = _free_ports(1)
    _reserved_by(reservations, port, _a_finished_pid())

    with _only_these_are_selectable((port,)):
        assert _allocator(reservations).get() == port


def test_allocator_releases_the_ports_of_a_run_that_recycled_its_pid(tmp_path: Path):
    # a new process must not be locked out by entries an older one with the same PID left behind
    reservations = tmp_path / "ports.json"
    (port,) = _free_ports(1)
    _reserved_by(reservations, port, os.getpid())

    with _only_these_are_selectable((port,)):
        assert _allocator(reservations).get() == port


def test_allocator_hands_out_a_port_once_and_gives_up_when_the_band_is_full(tmp_path: Path):
    selectable = _free_ports(3)
    reservations = tmp_path / "ports.json"

    with _only_these_are_selectable(selectable):
        allocator = _allocator(reservations)
        assert sorted(allocator.get() for _ in selectable) == sorted(selectable)

        with pytest.raises(NoFreeTCPPortError):
            allocator.get()


def test_allocator_records_a_handed_out_port_with_its_pid(tmp_path: Path):
    reservations = tmp_path / "ports.json"
    (port,) = _free_ports(1)

    with _only_these_are_selectable((port,)):
        assert _allocator(reservations).get() == port

    assert json.loads(reservations.read_text()) == {str(port): os.getpid()}


def test_the_band_stays_below_the_ports_swarm_publishes(tmp_path: Path):
    ports = get_port_allocator(reservations_path=tmp_path / "ports.json").ports

    assert ports.start == FIRST_TEST_PORT
    assert ports.stop < _DOCKER_SWARM_FIRST_PUBLISHED_PORT
