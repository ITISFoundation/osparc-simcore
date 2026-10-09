"""Utilities to safely share a single physical resource (docker stack, postgres template
database, S3 bucket, ...) across pytest-xdist worker processes.

pytest-xdist runs each worker as an independent pytest process with its own session, so
session/module-scoped fixtures execute once PER WORKER rather than once overall. These helpers
let a fixture detect it is running under xdist, derive a worker-unique name for resources that
must NOT be shared (e.g. a database clone), and coordinate exclusive setup/teardown of resources
that MUST be shared (e.g. one docker stack) via a cross-process file lock + reference-counted
registry, so exactly one worker performs the real setup/teardown while the others attach to it.
"""

import logging
import os
from collections.abc import Generator
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import Final

import pytest
from filelock import FileLock
from tenacity import retry, retry_if_exception_type, stop_after_delay, wait_fixed

from .logging_tools import ContextMessages, log_context

log = logging.getLogger(__name__)

# pytest-xdist's standard id for the controller process (i.e. any NON-xdist run)
WORKER_ID_MASTER: Final[str] = "master"

# name of the cross-process reader-writer lock guarding the docker daemon shared by xdist
# workers; used both by the `pytest_simcore.xdist_docker_daemon` plugin (per-test access)
# and by the shared-fixture churn sections in `pytest_simcore.docker_swarm`
DOCKER_DAEMON_LOCK_NAME: Final[str] = "docker_daemon"

# marker-file polls are cheap; coordination polls fast enough to keep tests snappy, while
# readiness of a full resource setup (container boot, DB template restore) polls slower
_POLL_INTERVAL: Final[timedelta] = timedelta(milliseconds=200)
_READY_POLL_INTERVAL: Final[timedelta] = timedelta(seconds=1)


class SharedResourceSetupError(RuntimeError):
    """Raised when the worker owning a shared resource's setup failed, so waiters can abort
    immediately instead of timing out waiting for a resource that will never become ready"""


def is_xdist_worker(request: pytest.FixtureRequest) -> bool:
    """True when running INSIDE a pytest-xdist worker process.

    Fixtures must branch on this to decide whether cross-worker coordination (shared
    registries/locks) or per-worker isolation is needed: a non-xdist run is a single process
    that cannot race itself, and touching the shared marker files there would only expose it
    to leftovers a crashed xdist session may have left in the machine-wide base temp dir.
    """
    return getattr(request.config, "workerinput", None) is not None


def get_worker_id(request: pytest.FixtureRequest) -> str:
    """Returns e.g. "gw0" for an xdist worker, or "master" outside xdist. Use it to build
    worker-unique resource names, only after `is_xdist_worker()` confirmed the worker context
    """
    workerinput = getattr(request.config, "workerinput", None)
    return WORKER_ID_MASTER if workerinput is None else workerinput["workerid"]


def get_max_xdist_workers(config: pytest.Config) -> int:
    """Maximum number of worker processes an xdist run of this session could spawn.

    NOTE: `max(..., cpu_count)` on purpose: sizing a shared resource's capacity (e.g. redis
    database banks) from the requested `-n` alone would break if the controller spawns more
    workers than the requested count, which cpu_count bounds from above.
    """
    numprocesses = config.getoption("numprocesses", default=None)
    if isinstance(numprocesses, str):  # "auto"/"detect"
        return os.cpu_count() or 1
    workers = int(numprocesses) if numprocesses else 0
    return max(workers, os.cpu_count() or 1)


def get_xdist_root_tmp_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Root temp dir shared by the controller and all xdist worker processes"""
    return tmp_path_factory.getbasetemp().parent


class SharedResourceRegistry:
    """Reference-counts concurrent users of one physical resource shared by xdist workers.

    `name` identifies the shared RESOURCE (one registry, i.e. one directory of marker files,
    per resource); every user (a worker's fixture instance) registers a unique `token` before
    using the resource and unregisters it once done, both under a cross-process file lock:
    - the caller for whom `register()` finds the registry empty owns the resource's real setup.
    - the caller for whom `unregister()` leaves the registry empty owns the resource's real
      teardown.
    A "ready" marker lets late-comers wait until the owner's setup has completed; a "failed"
    marker (see `mark_failed`) lets them abort immediately instead of waiting for a timeout.

    NOTE: this helper is intentionally framework-agnostic (only `pytest` types in signatures)
    and a natural candidate for extraction to a shared production library in a future PR.
    NOTE: marker files live in a machine-wide base temp dir (`getbasetemp().parent`) and
    therefore SURVIVE the session that created them: a process hard-killed mid-setup leaks its
    token, and only the timeout paths below can surface that (with an actionable message
    pointing at the leftover files). Non-xdist runs must not use this registry at all.
    """

    def __init__(self, root_tmp_path: Path, name: str) -> None:
        self.name = name
        self._lock_path = root_tmp_path / f"{name}.lock"
        self._registry_dir = root_tmp_path / f"{name}.registry"
        self._ready_marker = root_tmp_path / f"{name}.ready"
        self._failed_marker = root_tmp_path / f"{name}.failed"
        self._registry_dir.mkdir(parents=True, exist_ok=True)

    def _tokens(self) -> list[Path]:
        return list(self._registry_dir.glob("*.token"))

    def register(self, token: str) -> bool:
        """Registers `token` (touching a marker file, idempotent if it already exists).

        Returns True if the caller owns the resource's real setup. A new owner (registry empty,
        so NO live waiters) also clears stale "ready"/"failed" markers left over by a previous,
        crashed session before handing out ownership.
        """
        with (
            log_context(
                logging.INFO,
                ContextMessages(
                    starting=f"registering {token} for shared resource {self.name}",
                    done=lambda: (
                        f"{token} OWNS setup of {self.name}" if owns_setup else f"{token} attached to {self.name}"
                    ),
                ),
                logger=log,
            ),
            FileLock(str(self._lock_path)),
        ):
            owns_setup = not self._tokens()
            if owns_setup:
                self._ready_marker.unlink(missing_ok=True)
                self._failed_marker.unlink(missing_ok=True)
            (self._registry_dir / f"{token}.token").touch()
            return owns_setup

    def unregister(self, token: str) -> bool:
        """Unregisters `token`. Returns True if the caller owns the resource's real teardown.

        NOTE: intentionally does NOT clear the "failed" marker, so late waiters keep failing
        fast: only a subsequent setup-owner clears it in `register()` (see above).
        """
        with (
            log_context(
                logging.INFO,
                ContextMessages(
                    starting=f"unregistering {token} from shared resource {self.name}",
                    done=lambda: (
                        f"{token} OWNS teardown of {self.name}" if owns_teardown else f"{token} left {self.name}"
                    ),
                ),
                logger=log,
            ),
            FileLock(str(self._lock_path)),
        ):
            (self._registry_dir / f"{token}.token").unlink(missing_ok=True)
            owns_teardown = not self._tokens()
            if owns_teardown:
                self._ready_marker.unlink(missing_ok=True)
            return owns_teardown

    def mark_ready(self) -> None:
        with log_context(logging.INFO, f"shared resource {self.name} marked ready", logger=log):
            self._ready_marker.touch()

    def mark_failed(self) -> None:
        """Signals waiters that the owner's setup failed and the resource will never be ready"""
        with log_context(logging.WARNING, f"shared resource {self.name} marked FAILED", logger=log):
            self._failed_marker.touch()

    def wait_ready(self, *, timeout: timedelta) -> None:
        """Blocks until the owner signals readiness, failing fast if it signals failure

        Raises:
            SharedResourceSetupError: the owner's setup failed
            TimeoutError: neither ready nor failed within `timeout` (e.g. the owner was
                hard-killed and leaked its token: the message points at the leftover files)
        """

        @retry(
            stop=stop_after_delay(timeout),
            wait=wait_fixed(_READY_POLL_INTERVAL),
            retry=retry_if_exception_type(AssertionError),  # only "not ready YET" is retried
            reraise=True,
        )
        def _check_ready() -> None:
            if self._failed_marker.exists():
                msg = f"Setup of shared resource failed (owner reported {self._failed_marker})"
                raise SharedResourceSetupError(msg)
            assert self._ready_marker.exists(), f"shared resource not ready yet: {self._ready_marker}"

        with log_context(
            logging.INFO,
            ContextMessages(
                starting=f"waiting (up to {timeout}) for shared resource {self.name} to become ready",
                done=f"{self.name} is ready",
                raised=f"{self.name} NEVER became ready",
            ),
            logger=log,
        ):
            try:
                _check_ready()
            except AssertionError as err:
                msg = (
                    f"Timed out waiting for shared resource (marker {self._ready_marker}). "
                    f"If no test session is currently running, leftover token files from a "
                    f"crashed session are poisoning it: remove {self._registry_dir} "
                    f"(and {self._ready_marker}, {self._failed_marker}) and retry."
                )
                raise TimeoutError(msg) from err


class ReaderWriterLock:
    """Cross-process reader-writer lock for xdist workers sharing one resource (e.g. the
    docker daemon): most tests ("readers") may run concurrently with each other, but a few
    sensitive tests ("writers") need to run with NO other test concurrently touching the
    resource, across every worker - e.g. because they list/inspect ALL matching entities and
    are sensitive to interference from unrelated, concurrent churn by other workers.
    """

    def __init__(self, root_tmp_path: Path, name: str) -> None:
        self.name = name
        self._control_lock_path = root_tmp_path / f"{name}.rw.lock"
        self._readers_dir = root_tmp_path / f"{name}.rw.readers"
        self._writer_marker = root_tmp_path / f"{name}.rw.writer"
        self._readers_dir.mkdir(parents=True, exist_ok=True)

    def _has_readers(self) -> bool:
        return any(self._readers_dir.iterdir())

    @contextmanager
    def read_lock(self, token: str, *, timeout: timedelta = timedelta(minutes=5)) -> Generator[None]:
        """Waits for any in-progress writer to finish, then registers as a reader."""

        @retry(
            stop=stop_after_delay(timeout),
            wait=wait_fixed(_POLL_INTERVAL),
            retry=retry_if_exception_type(AssertionError),
            reraise=True,
        )
        def _register_reader() -> None:
            with FileLock(str(self._control_lock_path)):
                assert not self._writer_marker.exists(), "a writer holds the lock"
                (self._readers_dir / f"{token}.reader").touch()

        try:
            _register_reader()
        except AssertionError as err:
            msg = f"Timed out waiting for an active writer to release {self._writer_marker}"
            raise TimeoutError(msg) from err
        log.info("reader %s entered %s", token, self.name)
        try:
            yield
        finally:
            with FileLock(str(self._control_lock_path)):
                (self._readers_dir / f"{token}.reader").unlink(missing_ok=True)
            log.info("reader %s left %s", token, self.name)

    @contextmanager
    def write_lock(self, *, token: str | None = None, timeout: timedelta = timedelta(minutes=5)) -> Generator[None]:
        """Waits to become the sole writer, then waits for all current readers to finish,
        blocking new readers/writers in the meantime; releases both on exit.

        `token` is optional and purely diagnostic: written inside the writer marker to make it
        obvious WHICH worker holds the lock when inspecting the marker files by hand.
        """

        @retry(
            stop=stop_after_delay(timeout),
            wait=wait_fixed(_POLL_INTERVAL),
            retry=retry_if_exception_type(AssertionError),
            reraise=True,
        )
        def _acquire_writer_slot() -> None:
            with FileLock(str(self._control_lock_path)):
                assert not self._writer_marker.exists(), "another writer holds the lock"
                self._writer_marker.write_text(token or "writer")

        @retry(
            stop=stop_after_delay(timeout),
            wait=wait_fixed(_POLL_INTERVAL),
            retry=retry_if_exception_type(AssertionError),
            reraise=True,
        )
        def _drain_readers() -> None:
            with FileLock(str(self._control_lock_path)):
                assert not self._has_readers(), "readers are still active"

        # phase 1: acquire the writer slot (`timeout` budget of its own)
        with log_context(
            logging.INFO,
            (
                f"writer {token or 'writer'} waiting to start on {self.name}",
                lambda: f"writer got exclusive slot on {self.name}",
            ),
            logger=log,
        ):
            try:
                _acquire_writer_slot()
            except AssertionError as err:
                msg = f"Timed out waiting to become the writer for {self._writer_marker}"
                raise TimeoutError(msg) from err
        # phase 2: drain the readers already in the section (fresh `timeout` budget, so a
        # slow phase 1 cannot starve the drain phase)
        with log_context(
            logging.INFO,
            (
                f"writer {token or 'writer'} waiting for readers to drain on {self.name}",
                lambda: f"writer section STARTED on {self.name}",
            ),
            logger=log,
        ):
            try:
                _drain_readers()
            except AssertionError as err:
                msg = f"Timed out waiting for readers to finish for {self._writer_marker}"
                raise TimeoutError(msg) from err
        try:
            yield
        finally:
            with FileLock(str(self._control_lock_path)):
                self._writer_marker.unlink(missing_ok=True)
            log.info("writer %s left %s", token or "writer", self.name)
