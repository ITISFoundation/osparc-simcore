"""Tests for the cross-run docker swarm membership/ownership coordination"""

import getpass
import os
from pathlib import Path

import pytest
from pytest_simcore.helpers.swarm_coordination import (
    SwarmCoordinator,
    get_coordination_dir,
)


class _FakeSwarm:
    def __init__(self, *, up: bool = False, cluster_id: str = "") -> None:
        self.up = up
        self.cluster_id = cluster_id if up else ""
        self.init_calls = 0
        self.leave_calls = 0
        self._created = 0

    def is_up(self) -> bool:
        return self.up

    def id(self) -> str:
        return self.cluster_id

    def init(self) -> None:
        self.init_calls += 1
        self.up = True
        self._created += 1
        self.cluster_id = f"swarm-{self._created}"

    def leave(self) -> None:
        self.leave_calls += 1
        self.up = False
        self.cluster_id = ""


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
        swarm_id=swarm.id,
    )


def _leave(coordinator: SwarmCoordinator, swarm: _FakeSwarm, token: str, *, keep_up: bool = False) -> bool:
    return coordinator.leave(token=token, keep_up=keep_up, swarm_id=swarm.id, leave_swarm=swarm.leave)


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


def test_unreadable_member_tokens_are_pruned_by_the_default_liveness_check(tmp_path: Path, swarm: _FakeSwarm):
    # regression: a malformed token must be dropped WITHOUT any PID check seeing it — the
    # previous sentinel PID -1 made os.kill() succeed (it targets the whole process group),
    # so with the real pid_is_alive such a token survived and blocked the swarm from being left
    coordinator = SwarmCoordinator(tmp_path / "daemon")  # default is_alive=pid_is_alive
    _join(coordinator, swarm, "run-a", os.getpid())
    (tmp_path / "daemon" / "members" / "junk").write_text("not-a-pid")

    assert _leave(coordinator, swarm, "run-a") is True
    assert not (tmp_path / "daemon" / "members" / "junk").exists()


def test_coordination_dir_is_daemon_scoped():
    a = get_coordination_dir("daemon-id-1")
    b = get_coordination_dir("daemon-id-2")

    assert a != b
    assert get_coordination_dir("daemon-id-1") == a
    assert a.name.startswith("daemon-")


def test_coordination_dir_is_user_scoped(monkeypatch: pytest.MonkeyPatch):
    # two POSIX users of one daemon must not share the root: neither can write into the
    # other's (non-group-writable) /tmp state, and a foreign dead member could not be pruned
    monkeypatch.setattr(getpass, "getuser", lambda: "alice")
    alice = get_coordination_dir("daemon-id-1")
    monkeypatch.setattr(getpass, "getuser", lambda: "bob")
    bob = get_coordination_dir("daemon-id-1")

    assert alice != bob
    assert alice.parent.name == "pytest-simcore-alice"
    assert bob.parent.name == "pytest-simcore-bob"


def test_user_swarm_replacing_a_kept_pytest_swarm_is_never_left(tmp_path: Path, alive: set[int], swarm: _FakeSwarm):
    # regression: with only a bare marker, a `--keep-docker-up`/crash-survived "pytest" lineage
    # was trusted blindly: after the user replaced the swarm, the last run force-left THEIR swarm
    coordinator = _coordinator(tmp_path, alive)
    _join(coordinator, swarm, "run-a", 100)  # pytest owns swarm-1
    assert _leave(coordinator, swarm, "run-a", keep_up=True) is False  # lineage pytest kept

    # the user takes over: leaves pytest's swarm and initializes their own
    swarm.up = False
    swarm.cluster_id = ""
    swarm.up = True
    swarm.cluster_id = "user-swarm"

    later = _coordinator(tmp_path, alive)
    _join(later, swarm, "run-b", 200)  # lineage names swarm-1, daemon says user-swarm: external
    assert _leave(later, swarm, "run-b") is False
    assert swarm.up
    assert swarm.leave_calls == 0


def test_swarm_replaced_between_join_and_leave_is_never_left(tmp_path: Path, alive: set[int], swarm: _FakeSwarm):
    # the ID is re-checked at leave time too: a replacement that slipped between the last join
    # and the session end must still not be left
    coordinator = _coordinator(tmp_path, alive)
    _join(coordinator, swarm, "run-a", 100)

    swarm.up = False
    swarm.cluster_id = ""
    swarm.up = True
    swarm.cluster_id = "user-swarm"

    assert _leave(coordinator, swarm, "run-a") is False
    assert swarm.up
    assert swarm.leave_calls == 0


def test_replacement_is_demoted_in_the_lineage_marker(tmp_path: Path, alive: set[int], swarm: _FakeSwarm):
    coordinator = _coordinator(tmp_path, alive)
    _join(coordinator, swarm, "run-a", 100)

    swarm.up = False
    swarm.cluster_id = ""
    swarm.up = True
    swarm.cluster_id = "user-swarm"

    assert _leave(coordinator, swarm, "run-a") is False

    # the demarking persists: every subsequent run sees external/user-swarm right away
    assert (tmp_path / "daemon" / "swarm_lineage").read_text() == "external user-swarm"
