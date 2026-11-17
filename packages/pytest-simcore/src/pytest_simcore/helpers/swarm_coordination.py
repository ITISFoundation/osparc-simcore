"""Cross-session coordination for the docker swarm shared by concurrent pytest runs.

The stack/service *names* are already run-scoped (see stack_names.py), but the swarm itself is
a single daemon-wide resource: the daemon must be in swarm mode while ANY run needs it and must
NOT be torn down while other runs still use it. Every run against the same daemon therefore
coordinates through a per-daemon directory (keyed by a hash of the daemon ID, under a per-user
temp root), using only lock files so runs never have to wait for each other:

- each run registers a member token named after a digest of the run's shared temp dir and holding
  the PID of the process whose death ends the run (the session's own process, or the xdist
  controller), so crashed runs are detected by PID liveness and pruned
- the first run that finds the daemon NOT in swarm mode initializes it and marks the swarm as
  pytest-owned: the lineage file then reads ``pytest <clusterID>``, the ID being the swarm's
  cluster ID at creation time
- a run that finds an up swarm either WITHOUT lineage or whose lineage names a DIFFERENT cluster
  ID (the user replaced the swarm under a kept marker) marks it ``external <clusterID>``: pytest
  then never leaves it; the ID is re-checked before leaving for the same reason
- leaving removes the run's token; only the LAST live member leaves the swarm (unless
  ``--keep-docker-up``), so a crashed run's leftover swarm is cleaned up by the next run that
  ends up last (adoption) while an external swarm is never touched

All state transitions happen under one file lock, so joining/leaving runs cannot interleave.

NOTE: the root is per-user on purpose: two POSIX accounts sharing one docker daemon cannot share
a coordination root in /tmp without group setup and symlink-attack care, and a foreign dead
member could not be pruned across users anyway (unlink would fail). Each user's runs coordinate
among themselves; a swarm another user's runs created surfaces as unmarked (hence external) and
is never left by them.
"""

import getpass
import hashlib
import logging
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Final

from annotated_types import doc
from filelock import FileLock

_logger: Final[logging.Logger] = logging.getLogger(__name__)

_LINEAGE_PYTEST: Final[Annotated[str, doc("swarm lineage marker: pytest owns it and may leave it")]] = "pytest"
_LINEAGE_EXTERNAL: Final[Annotated[str, doc("swarm lineage marker: the swarm is the user's, never leave it")]] = (
    "external"
)

_MEMBERS_DIR_NAME: Final[str] = "members"
_LINEAGE_FILE_NAME: Final[str] = "swarm_lineage"
_LOCK_FILE_NAME: Final[str] = "swarm.lock"
_COORDINATION_ROOT_NAME: Final[str] = "pytest-simcore"
_DAEMON_DIR_PREFIX: Final[str] = "daemon-"
_DAEMON_ID_HASH_LEN: Final[
    Annotated[int, doc("hex chars of the daemon-ID hash naming the per-daemon coordination dir")]
] = 12

_DEFAULT_LOCK_TIMEOUT: Final[
    Annotated[float, doc("lock wait budget: a swarm init takes ~15 s max, so this is slack")]
] = 5 * 60


def pid_is_alive(pid: int) -> bool:
    """True when a process with this PID currently exists (any other user counts too)

    NOTE: signal 0 is the null signal: the kernel runs the usual permission/existence checks
    but delivers nothing, so os.kill(pid, 0) is the POSIX liveness probe (see os.kill docs).
    A PermissionError therefore means the process exists but belongs to another user.
    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def get_coordination_dir(daemon_id: str) -> Path:
    """Directory coordinating the pytest runs of ONE user against one docker daemon

    NOTE: keyed by the daemon ID (not DOCKER_HOST) so that runs pointing at the same daemon
    through different URLs (e.g. a remote daemon reachable over several endpoints) still
    coordinate, while runs against different daemons never do.
    """
    digest = hashlib.sha1(daemon_id.encode(), usedforsecurity=False).hexdigest()[:_DAEMON_ID_HASH_LEN]
    root = f"{_COORDINATION_ROOT_NAME}-{getpass.getuser()}"
    return Path(tempfile.gettempdir()) / root / f"{_DAEMON_DIR_PREFIX}{digest}"


class SwarmCoordinator:
    """File-based membership/ownership of the docker swarm of one daemon, shared across processes"""

    def __init__(
        self,
        root: Path,
        *,
        is_alive: Callable[[int], bool] = pid_is_alive,
        lock_timeout: float = _DEFAULT_LOCK_TIMEOUT,
    ) -> None:
        self._members_dir = root / _MEMBERS_DIR_NAME
        self._lineage_file = root / _LINEAGE_FILE_NAME
        self._lock_path = root / _LOCK_FILE_NAME
        self._is_alive = is_alive
        self._lock_timeout = lock_timeout
        self._members_dir.mkdir(parents=True, exist_ok=True)

    def has_member(self, token: str) -> bool:
        """True when this run registered as a swarm member (in this or a sibling process)"""
        return (self._members_dir / token).exists()

    def join(
        self,
        *,
        token: str,
        watched_pid: int,
        swarm_is_up: Callable[[], bool],
        init_swarm: Callable[[], None],
        swarm_id: Callable[[], str],
    ) -> None:
        """Registers this run as a swarm member, initializing the swarm when it is down

        `swarm_id` returns the daemon's current swarm cluster ID (empty when out of swarm mode),
        binding the lineage marker to the exact swarm it was written for.

        NOTE: idempotent, so calling it from every module-scoped fixture setup of a session is
        safe; it also RE-initializes the swarm if someone left it while this run was idle.
        """
        with FileLock(str(self._lock_path), timeout=self._lock_timeout):
            self._prune_dead_members()
            if not swarm_is_up():
                _logger.info("docker swarm is down: initializing it and marking it pytest-owned")
                init_swarm()
                self._write_lineage(_LINEAGE_PYTEST, swarm_id())
            else:
                lineage, lineage_id = self._read_lineage()
                if lineage != _LINEAGE_PYTEST or lineage_id != swarm_id():
                    # unmarked, or pytest lineage naming a DIFFERENT cluster ID: the user replaced
                    # the swarm under a kept marker. assume it is theirs: never leave it
                    _logger.info(
                        "joining a docker swarm pytest does not own (no matching lineage): "
                        "marking it external, it will never be left"
                    )
                    self._write_lineage(_LINEAGE_EXTERNAL, swarm_id())
            (self._members_dir / token).write_text(f"{watched_pid}")

    def leave(self, *, token: str, keep_up: bool, swarm_id: Callable[[], str], leave_swarm: Callable[[], None]) -> bool:
        """Unregisters this run; leaves the swarm only when it was the last live member

        Returns True when the swarm was actually left. With `keep_up` the swarm is never left and
        the pytest lineage marker is kept, so a later run adopts and eventually cleans it up.
        """
        with FileLock(str(self._lock_path), timeout=self._lock_timeout):
            (self._members_dir / token).unlink(missing_ok=True)
            self._prune_dead_members()
            if any(self._members_dir.iterdir()):
                _logger.info("other pytest runs still use the docker swarm: leaving it up for them")
                return False

            lineage, lineage_id = self._read_lineage()
            if lineage != _LINEAGE_PYTEST:
                # external (the user's) or unknown lineage: never leave what we did not create
                return False
            if lineage_id != swarm_id():
                # the daemon's current swarm is NOT the one pytest created (e.g. the user
                # replaced it while a kept marker survived): demark it and keep off
                _logger.info("swarm cluster ID no longer matches the pytest lineage: marking it external")
                self._write_lineage(_LINEAGE_EXTERNAL, swarm_id())
                return False
            if keep_up:
                return False

            leave_swarm()
            self._lineage_file.unlink(missing_ok=True)
            return True

    def _write_lineage(self, lineage: str, cluster_id: str) -> None:
        self._lineage_file.write_text(f"{lineage} {cluster_id}")

    def _read_lineage(self) -> tuple[str | None, str]:
        try:
            content = self._lineage_file.read_text()
        except OSError:
            return None, ""
        lineage, _, cluster_id = content.partition(" ")
        return lineage, cluster_id

    def _prune_dead_members(self) -> None:
        for token_file in self._members_dir.iterdir():
            try:
                watched_pid = int(token_file.read_text())
            except OSError, ValueError:
                # unreadable token: drop it without a liveness check, since no sentinel PID can be
                # passed to os.kill(): it reports success for -1 (the whole process group)
                _logger.warning("dropping unreadable swarm member token %s", token_file)
                token_file.unlink(missing_ok=True)
                continue
            if not self._is_alive(watched_pid):
                _logger.info("dropping swarm member token %s of dead process %s", token_file, watched_pid)
                token_file.unlink(missing_ok=True)
