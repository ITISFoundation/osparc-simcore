# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import threading
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from filelock import Timeout
from pytest_simcore.helpers.xdist import (
    ReaderWriterLock,
    SharedResourceSetupError,
    is_xdist_controller,
    read_shared_resources,
    record_shared_resource,
    run_once_across_workers,
)


class _SetupBoomError(RuntimeError):
    pass


@pytest.fixture
def tmp_path_factory_of_run(tmp_path: Path) -> Any:
    """mimics a worker's factory: its base temp dir is a child of the run's shared dir (`tmp_path`)"""
    return SimpleNamespace(getbasetemp=lambda: tmp_path / "popen-gw0")


@pytest.fixture
def worker_request() -> Any:
    return SimpleNamespace(config=SimpleNamespace(workerinput={"workerid": "gw0"}))


@pytest.fixture
def master_request() -> Any:
    return SimpleNamespace(config=SimpleNamespace(workerinput=None))


def test_run_once_always_runs_without_xdist(master_request, tmp_path_factory_of_run):
    for _ in range(2):
        with run_once_across_workers(
            master_request, tmp_path_factory_of_run, "res", timeout=timedelta(seconds=1)
        ) as is_first:
            assert is_first is True


def test_run_once_runs_only_in_the_first_worker_call(worker_request, tmp_path_factory_of_run):
    results = []
    for _ in range(3):
        with run_once_across_workers(
            worker_request, tmp_path_factory_of_run, "res", timeout=timedelta(seconds=1)
        ) as is_first:
            results.append(is_first)

    assert results == [True, False, False]


def test_run_once_failure_makes_next_callers_fail_fast(worker_request, tmp_path_factory_of_run):
    with (
        pytest.raises(_SetupBoomError),
        run_once_across_workers(worker_request, tmp_path_factory_of_run, "res", timeout=timedelta(seconds=1)),
    ):
        raise _SetupBoomError

    with (
        pytest.raises(SharedResourceSetupError, match="_SetupBoomError"),
        run_once_across_workers(worker_request, tmp_path_factory_of_run, "res", timeout=timedelta(seconds=1)),
    ):
        pytest.fail("the body must not run")


def test_run_once_other_workers_wait_for_the_setup(worker_request, tmp_path_factory_of_run):
    setup_started = threading.Event()
    setup_can_finish = threading.Event()

    def _first_worker() -> None:
        with run_once_across_workers(
            worker_request, tmp_path_factory_of_run, "res", timeout=timedelta(seconds=5)
        ) as is_first:
            assert is_first
            setup_started.set()
            assert setup_can_finish.wait(timeout=5)

    thread = threading.Thread(target=_first_worker)
    thread.start()
    assert setup_started.wait(timeout=5)

    # still setting up: a second worker times out waiting
    with (
        pytest.raises(Timeout),
        run_once_across_workers(worker_request, tmp_path_factory_of_run, "res", timeout=timedelta(milliseconds=200)),
    ):
        pytest.fail("the body must not run")

    setup_can_finish.set()
    thread.join(timeout=5)

    with run_once_across_workers(
        worker_request, tmp_path_factory_of_run, "res", timeout=timedelta(seconds=1)
    ) as is_first:
        assert is_first is False


def test_shared_resources_are_recorded_by_workers_and_read_by_the_controller(
    worker_request, tmp_path_factory_of_run, tmp_path
):
    record_shared_resource(worker_request, tmp_path_factory_of_run, kind="stack", name="ops")
    record_shared_resource(worker_request, tmp_path_factory_of_run, kind="swarm")

    controller_config = SimpleNamespace(_tmp_path_factory=SimpleNamespace(getbasetemp=lambda: tmp_path))
    assert read_shared_resources(controller_config) == [{"kind": "stack", "name": "ops"}, {"kind": "swarm"}]  # type: ignore[arg-type]


def test_shared_resources_are_not_recorded_without_xdist(master_request, tmp_path_factory_of_run, tmp_path):
    record_shared_resource(master_request, tmp_path_factory_of_run, kind="swarm")

    controller_config = SimpleNamespace(_tmp_path_factory=SimpleNamespace(getbasetemp=lambda: tmp_path))
    assert read_shared_resources(controller_config) == []  # type: ignore[arg-type]


@pytest.mark.parametrize("plugins", [{"dsession"}, set()])
def test_is_xdist_controller_requires_the_dsession_plugin(plugins):
    config = SimpleNamespace(pluginmanager=SimpleNamespace(has_plugin=lambda name: name in plugins))
    assert is_xdist_controller(config) is ("dsession" in plugins)  # type: ignore[arg-type]


def test_write_lock_releases_marker_when_reader_drain_times_out(tmp_path_factory):
    """a writer whose drain phase times out must NOT leave its marker behind: a stale marker
    would poison every subsequent reader/writer acquisition until removed by hand
    """
    lock = ReaderWriterLock(tmp_path_factory.mktemp("rw"), "daemon")
    stuck_reader = "stuck-reader"
    giving_up_writer = "giving-up-writer"
    next_writer = "next-writer"

    writer_never_started = lock.write_lock(token=giving_up_writer, timeout=timedelta(milliseconds=100))
    with lock.read_lock(token=stuck_reader), pytest.raises(TimeoutError), writer_never_started:
        pass  # the writer must never enter its section while the reader is stuck

    # the abandoned writer's marker must be gone: a later writer acquires cleanly
    with lock.write_lock(token=next_writer, timeout=timedelta(seconds=5)):
        pass
