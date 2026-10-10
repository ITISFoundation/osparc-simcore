"""Helpers to share physical resources (docker stack, postgres template, ...) across pytest-xdist workers.

Every xdist worker is an independent pytest process, so session/module fixtures run once PER WORKER.
Resources that must exist only once are set up by the first worker (`run_once_across_workers`) and,
if they need cleanup, recorded for the xdist controller to remove at session end (`record_shared_resource`).
"""

import logging
import os
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import Final

import pytest
from common_library.json_serialization import json_dumps, json_loads
from filelock import FileLock
from tenacity import retry, retry_if_exception_type, stop_after_delay, wait_fixed

from .logging_tools import log_context

log = logging.getLogger(__name__)

# pytest-xdist's standard id for the controller process (i.e. any NON-xdist run)
WORKER_ID_MASTER: Final[str] = "master"

_POLL_INTERVAL: Final[timedelta] = timedelta(milliseconds=200)
_SHARED_RESOURCES_MANIFEST: Final[str] = "shared_resources.jsonl"


class SharedResourceSetupError(RuntimeError):
    """The first worker failed to set a shared resource up, so the others fail fast instead of retrying"""


def is_xdist_worker(request: pytest.FixtureRequest) -> bool:
    """True when running INSIDE a pytest-xdist worker process"""
    return getattr(request.config, "workerinput", None) is not None


def is_xdist_controller(config: pytest.Config) -> bool:
    """True in the xdist process that spawns the workers (it runs no tests)"""
    return config.pluginmanager.has_plugin("dsession")


def get_worker_id(request: pytest.FixtureRequest) -> str:
    """Returns e.g. "gw0" for an xdist worker, or "master" outside xdist"""
    workerinput = getattr(request.config, "workerinput", None)
    return WORKER_ID_MASTER if workerinput is None else workerinput["workerid"]


def get_max_xdist_workers(config: pytest.Config) -> int:
    """Maximum number of worker processes an xdist run of this session could spawn.

    NOTE: bounded below by `cpu_count` because the controller may spawn more workers than `-n`.
    """
    numprocesses = config.getoption("numprocesses", default=None)
    if isinstance(numprocesses, str):  # "auto"/"detect"
        return os.cpu_count() or 1
    workers = int(numprocesses) if numprocesses else 0
    return max(workers, os.cpu_count() or 1)


def get_xdist_root_tmp_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Temp dir of the current run, shared by the controller and all its workers"""
    return tmp_path_factory.getbasetemp().parent


@contextmanager
def run_once_across_workers(
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
    name: str,
    *,
    timeout: timedelta,
) -> Iterator[bool]:
    """Yields True to the one worker that must set the resource `name` up inside the block.

    The other workers wait for it and get False. Outside xdist it always yields True.

    Raises:
        SharedResourceSetupError: the first worker failed its setup
        filelock.Timeout: the first worker did not finish within `timeout`
    """
    if not is_xdist_worker(request):
        yield True
        return

    root = get_xdist_root_tmp_path(tmp_path_factory)
    done, failed = root / f"{name}.done", root / f"{name}.failed"

    with FileLock(root / f"{name}.lock", timeout=timeout.total_seconds()):
        if failed.exists():
            msg = f"Setup of {name} failed in another worker: {failed.read_text()}"
            raise SharedResourceSetupError(msg)
        if not done.exists():
            try:
                with log_context(logging.INFO, f"{get_worker_id(request)} sets up shared {name}", logger=log):
                    yield True
            except BaseException as err:
                failed.write_text(repr(err))
                raise
            done.touch()
            return
    yield False


def record_shared_resource(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory, **resource: str
) -> None:
    """Records a resource the xdist controller must remove at session end (see `read_shared_resources`).

    No-op outside xdist, where the fixtures tear their own resources down.
    """
    if not is_xdist_worker(request):
        return
    manifest = get_xdist_root_tmp_path(tmp_path_factory) / _SHARED_RESOURCES_MANIFEST
    with manifest.open("a") as fh:
        fh.write(f"{json_dumps(resource)}\n")


def read_shared_resources(config: pytest.Config) -> list[dict[str, str]]:
    """Resources recorded by the workers, in recording order. To be called from the controller."""
    # NOTE: the controller has no fixtures; its base temp dir is the parent of every worker's one
    root: Path = config._tmp_path_factory.getbasetemp()  # type: ignore[attr-defined]  # noqa: SLF001
    manifest = root / _SHARED_RESOURCES_MANIFEST
    if not manifest.exists():
        return []
    return [json_loads(line) for line in manifest.read_text().splitlines()]


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
        try:
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
        except BaseException:
            # the writer section was NEVER entered: release the slot we hold, or a timed-out
            # writer would leave its marker behind and poison every later reader/writer
            with FileLock(str(self._control_lock_path)):
                self._writer_marker.unlink(missing_ok=True)
            raise
        try:
            yield
        finally:
            with FileLock(str(self._control_lock_path)):
                self._writer_marker.unlink(missing_ok=True)
            log.info("writer %s left %s", token or "writer", self.name)
