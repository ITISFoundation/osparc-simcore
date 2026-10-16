"""Tests for the cross-run docker swarm membership/ownership coordination"""

from pathlib import Path

import pytest
from pytest_simcore.helpers.swarm_coordination import (
    SwarmCoordinator,
    get_coordination_dir,
)


class _FakeSwarm:
    def __init__(self, *, up: bool = False) -> None:
        self.up = up
        self.init_calls = 0
        self.leave_calls = 0

    def is_up(self) -> bool:
        return self.up

    def init(self) -> None:
        self.init_calls += 1
        self.up = True

    def leave(self) -> None:
        self.leave_calls += 1
        self.up = False


@pytest.fixture(name="swarm")
def _swarm_fixture() -> _FakeSwarm:
    return _FakeSwarm()


@pytest.fixture(name="alive")
def _alive_fixture() -> set[int]:
    """PIDs considered alive; tests remove/add entries to simulate process death"""
    return {100, 200, 300}


def _coordinator(tmp_path: Path, alive: set[int]) -> SwarmCoordinator:
    return SwarmCoordinator(tmp_path / "daemon", is_alive=lambda pid: pid in alive)


def _join(coordinator: SwarmCoordinator, swarm: _FakeSwarm, token: str, pid: int) -> None:
    coordinator.join(
        token=token,
        watched_pid=pid,
        swarm_is_up=swarm.is_up,
        init_swarm=swarm.init,
    )


def _leave(coordinator: SwarmCoordinator, swarm: _FakeSwarm, token: str, *, keep_up: bool = False) -> bool:
    return coordinator.leave(token=token, keep_up=keep_up, leave_swarm=swarm.leave)


def test_first_join_initializes_and_marks_lineage(tmp_path: Path, alive: set[int], swarm: _FakeSwarm):
    coordinator = _coordinator(tmp_path, alive)
    _join(coordinator, swarm, "run-a", 100)

    assert swarm.up
    assert swarm.init_calls == 1
    assert coordinator.has_member("run-a")


def test_join_is_idempotent(tmp_path: Path, alive: set[int], swarm: _FakeSwarm):
    coordinator = _coordinator(tmp_path, alive)
    _join(coordinator, swarm, "run-a", 100)
    _join(coordinator, swarm, "run-a", 100)  # e.g. every module-scoped fixture setup

    assert swarm.init_calls == 1


def test_second_run_joins_without_reinitializing(tmp_path: Path, alive: set[int], swarm: _FakeSwarm):
    coordinator = _coordinator(tmp_path, alive)
    _join(coordinator, swarm, "run-a", 100)
    _join(coordinator, swarm, "run-b", 200)

    assert swarm.init_calls == 1
    assert coordinator.has_member("run-a")
    assert coordinator.has_member("run-b")


def test_only_the_last_member_leaves_the_swarm(tmp_path: Path, alive: set[int], swarm: _FakeSwarm):
    coordinator = _coordinator(tmp_path, alive)
    _join(coordinator, swarm, "run-a", 100)
    _join(coordinator, swarm, "run-b", 200)

    assert _leave(coordinator, swarm, "run-a") is False
    assert swarm.up  # still needed by run-b

    assert _leave(coordinator, swarm, "run-b") is True
    assert not swarm.up
    assert swarm.leave_calls == 1


def test_keep_up_never_leaves_but_keeps_lineage(tmp_path: Path, alive: set[int], swarm: _FakeSwarm):
    coordinator = _coordinator(tmp_path, alive)
    _join(coordinator, swarm, "run-a", 100)

    assert _leave(coordinator, swarm, "run-a", keep_up=True) is False
    assert swarm.up
    assert swarm.leave_calls == 0

    # a later run (without keep-up) adopts the leftover swarm and cleans it up
    later = SwarmCoordinator(tmp_path / "daemon", is_alive=lambda pid: pid in alive)
    assert not later.has_member("run-b")
    _join(later, swarm, "run-b", 200)
    assert swarm.init_calls == 1  # reused, not re-initialized
    assert _leave(later, swarm, "run-b") is True
    assert not swarm.up


def test_crashed_run_does_not_block_a_live_member(tmp_path: Path, alive: set[int], swarm: _FakeSwarm):
    coordinator = _coordinator(tmp_path, alive)
    _join(coordinator, swarm, "run-a", 100)  # will "crash"
    _join(coordinator, swarm, "run-b", 200)

    alive.remove(100)  # run-a died: its token must be pruned, not waited for

    assert _leave(coordinator, swarm, "run-b") is True  # last live member -> leaves
    assert swarm.leave_calls == 1


def test_orphaned_swarm_is_adopted_and_eventually_left(tmp_path: Path, alive: set[int], swarm: _FakeSwarm):
    first = _coordinator(tmp_path, alive)
    _join(first, swarm, "run-a", 100)
    alive.remove(100)  # run-a crashed leaving the swarm up

    later = _coordinator(tmp_path, alive)
    _join(later, swarm, "run-b", 200)  # adopts: swarm up, lineage pytest, no live members
    assert swarm.init_calls == 1

    assert _leave(later, swarm, "run-b") is True
    assert not swarm.up


def test_external_swarm_is_never_left(tmp_path: Path, alive: set[int]):
    swarm = _FakeSwarm(up=True)  # the user's own swarm, no pytest lineage
    coordinator = _coordinator(tmp_path, alive)

    _join(coordinator, swarm, "run-a", 100)
    _join(coordinator, swarm, "run-b", 200)

    assert _leave(coordinator, swarm, "run-a") is False
    assert _leave(coordinator, swarm, "run-b") is False
    assert swarm.up
    assert swarm.leave_calls == 0
    assert swarm.init_calls == 0


def test_swarm_dropped_mid_run_is_reinitialized(tmp_path: Path, alive: set[int], swarm: _FakeSwarm):
    coordinator = _coordinator(tmp_path, alive)
    _join(coordinator, swarm, "run-a", 100)

    swarm.up = False  # someone left the swarm while this run was idle

    _join(coordinator, swarm, "run-a", 100)  # next module setup
    assert swarm.up
    assert swarm.init_calls == 2
    # re-initialized by pytest => pytest lineage again, so it will be left
    assert _leave(coordinator, swarm, "run-a") is True


def test_unknown_lineage_is_not_left(tmp_path: Path, alive: set[int], swarm: _FakeSwarm):
    coordinator = _coordinator(tmp_path, alive)
    _join(coordinator, swarm, "run-a", 100)

    (tmp_path / "daemon" / "swarm_lineage").write_text("bogus")

    assert _leave(coordinator, swarm, "run-a") is False
    assert swarm.up


def test_unreadable_member_tokens_are_pruned(tmp_path: Path, alive: set[int], swarm: _FakeSwarm):
    coordinator = _coordinator(tmp_path, alive)
    _join(coordinator, swarm, "run-a", 100)
    (tmp_path / "daemon" / "members" / "junk").write_text("not-a-pid")

    assert _leave(coordinator, swarm, "run-a") is True  # junk pruned, run-a was alone
    assert not (tmp_path / "daemon" / "members" / "junk").exists()


def test_coordination_dir_is_daemon_scoped():
    a = get_coordination_dir("daemon-id-1")
    b = get_coordination_dir("daemon-id-2")

    assert a != b
    assert get_coordination_dir("daemon-id-1") == a
    assert a.name.startswith("daemon-")
