# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import socket
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager

import pytest
from pytest_simcore.helpers.xdist_ports import (
    FIRST_TEST_PORT,
    NoFreeTCPPortError,
    TcpPortAllocator,
    get_port_allocator,
    is_port_free,
)

# just above the ranges the allocators hand out, so a concurrent test run cannot be holding these
_FREE_PORTS = range(FIRST_TEST_PORT + 8000, FIRST_TEST_PORT + 8010)
_CHECKOUT_UID = "0a0b0c0d"


@contextmanager
def _bound_ports(*ports: int) -> Iterator[None]:
    with ExitStack() as stack:
        for port in ports:
            sock = stack.enter_context(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
            sock.bind(("127.0.0.1", port))
        yield


def test_port_is_free_only_when_nothing_binds_it():
    port = next(p for p in _FREE_PORTS if is_port_free(p))

    with _bound_ports(port):
        assert is_port_free(port) is False
    assert is_port_free(port) is True


def test_allocator_skips_ports_bound_by_another_process():
    bound, *not_bound = _FREE_PORTS

    with _bound_ports(bound):
        port = TcpPortAllocator(_FREE_PORTS).get()

    assert port in not_bound


def test_allocator_hands_out_every_port_of_its_slice_once():
    ports = range(FIRST_TEST_PORT + 8020, FIRST_TEST_PORT + 8023)
    allocator = TcpPortAllocator(ports)

    assert sorted(allocator.get() for _ in ports) == sorted(ports)
    with pytest.raises(NoFreeTCPPortError):
        allocator.get()


@pytest.mark.parametrize("max_workers", [1, 4, 24])
def test_allocators_of_the_workers_of_a_run_have_disjoint_slices(max_workers: int):
    allocators = [
        get_port_allocator(
            worker_id=f"gw{index}",
            max_workers=max_workers,
            checkout_uid=_CHECKOUT_UID,
        )
        for index in range(max_workers)
    ]
    slices = [set(allocator.ports) for allocator in allocators]

    assert sum(len(one) for one in slices) == len(set().union(*slices))


@pytest.mark.parametrize("checkout_uid,other_checkout_uid", [("0a0b0c00", "0a0b0c01"), ("abcdef01", "abcdef02")])
def test_allocators_of_different_checkouts_have_disjoint_slices(checkout_uid: str, other_checkout_uid: str):
    allocator = get_port_allocator(worker_id="gw0", max_workers=4, checkout_uid=checkout_uid)
    other_allocator = get_port_allocator(worker_id="gw0", max_workers=4, checkout_uid=other_checkout_uid)

    assert set(allocator.ports).isdisjoint(other_allocator.ports)


@pytest.mark.parametrize("worker_id", ["master", "gw0", "gw3"])
def test_allocators_stay_out_of_the_ranges_other_processes_allocate_from(worker_id: str):
    ports = get_port_allocator(worker_id=worker_id, max_workers=4, checkout_uid=_CHECKOUT_UID).ports

    assert ports.start >= FIRST_TEST_PORT
    assert ports.stop < 30000  # docker swarm publishes service ports from here on
    assert ports.stop <= FIRST_TEST_PORT + 2 * 4000  # _CHECKOUT_SLOTS * _PORTS_PER_CHECKOUT


def test_a_run_without_workers_shares_the_slice_of_its_first_worker():
    # the controller runs no tests once xdist spawns workers, so both may use the same slice
    master = get_port_allocator(worker_id="master", max_workers=4, checkout_uid=_CHECKOUT_UID)
    worker = get_port_allocator(worker_id="gw0", max_workers=4, checkout_uid=_CHECKOUT_UID)

    assert master.ports == worker.ports
