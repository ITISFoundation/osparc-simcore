"""Utilities to safely share a single physical resource (docker stack, postgres template
database, S3 bucket, ...) across pytest-xdist worker processes.

pytest-xdist runs each worker as an independent pytest process with its own session, so
session/module-scoped fixtures execute once PER WORKER rather than once overall. These helpers
let a fixture detect it is running under xdist, derive a worker-unique name for resources that
must NOT be shared (e.g. a database clone), and coordinate exclusive setup/teardown of resources
that MUST be shared (e.g. one docker stack) via a cross-process file lock + reference-counted
registry, so exactly one worker performs the real setup/teardown while the others attach to it.
"""

from pathlib import Path

import pytest
from filelock import FileLock


def get_worker_id(request: pytest.FixtureRequest) -> str:
    """Returns e.g. "gw0" when running under pytest-xdist, or "master" otherwise"""
    workerinput = getattr(request.config, "workerinput", None)
    return "master" if workerinput is None else workerinput["workerid"]


def get_xdist_root_tmp_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Root temp dir shared by the controller and all xdist worker processes"""
    return tmp_path_factory.getbasetemp().parent


class SharedResourceRegistry:
    """Reference-counts concurrent users of one physical resource shared by xdist workers.

    Every user registers a unique `token` before using the resource and unregisters it once
    done, both under a cross-process file lock:
    - the caller for whom `register()` finds the registry empty owns the resource's real setup.
    - the caller for whom `unregister()` leaves the registry empty owns the resource's real
      teardown.
    A "ready" marker lets late-comers wait until the owner's setup has completed.
    """

    def __init__(self, root_tmp_path: Path, name: str) -> None:
        self._lock_path = root_tmp_path / f"{name}.lock"
        self._registry_dir = root_tmp_path / f"{name}.registry"
        self._ready_marker = root_tmp_path / f"{name}.ready"
        self._registry_dir.mkdir(parents=True, exist_ok=True)

    def _tokens(self) -> list[Path]:
        return list(self._registry_dir.glob("*.token"))

    def register(self, token: str) -> bool:
        """Registers `token`. Returns True if the caller owns the resource's real setup."""
        with FileLock(str(self._lock_path)):
            owns_setup = not self._tokens()
            (self._registry_dir / f"{token}.token").touch()
            return owns_setup

    def unregister(self, token: str) -> bool:
        """Unregisters `token`. Returns True if the caller owns the resource's real teardown."""
        with FileLock(str(self._lock_path)):
            (self._registry_dir / f"{token}.token").unlink(missing_ok=True)
            owns_teardown = not self._tokens()
            if owns_teardown:
                self._ready_marker.unlink(missing_ok=True)
            return owns_teardown

    def mark_ready(self) -> None:
        self._ready_marker.touch()

    def is_ready(self) -> bool:
        return self._ready_marker.exists()
