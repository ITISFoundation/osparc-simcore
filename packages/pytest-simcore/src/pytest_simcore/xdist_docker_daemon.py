"""Cross-worker locking for a docker daemon shared by pytest-xdist workers.

Load this plugin (`pytest_plugins = ["pytest_simcore.xdist_docker_daemon"]` in the suite's
root conftest) ONLY in suites that run under xdist against ONE shared docker stack: every
test then automatically holds the daemon lock, which is what makes the parallel speed-up
race-free (tests listing/inspecting ALL matching swarm services/networks are sensitive to
concurrent churn from unrelated modules). Suites that do not load this plugin are unaffected.
"""

import logging
from collections.abc import Iterator
from datetime import timedelta
from uuid import uuid4

import pytest

from .helpers.xdist import (
    DOCKER_DAEMON_LOCK_NAME,
    ReaderWriterLock,
    get_worker_id,
    get_xdist_root_tmp_path,
    is_xdist_worker,
)

_logger: logging.Logger = logging.getLogger(__name__)

_logged_activation: set[str] = set()  # worker ids already announced (per process, cheap guard)

# an exclusive writer must outwait any in-progress churn section holding the read lock
# (shared-stack deploy waits up to ~8 minutes, stack teardown drain up to ~6): pick a
# budget above the worst case so exclusive tests wait rather than spuriously time out
_EXCLUSIVE_LOCK_TIMEOUT: timedelta = timedelta(minutes=15)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "docker_exclusive: this test needs exclusive access to the shared docker daemon "
        "(no other test using the docker_daemon_access fixture running concurrently in any xdist worker)",
    )


@pytest.fixture(scope="session")
def _xdist_docker_daemon_lock(tmp_path_factory: pytest.TempPathFactory) -> ReaderWriterLock:
    return ReaderWriterLock(get_xdist_root_tmp_path(tmp_path_factory), DOCKER_DAEMON_LOCK_NAME)


@pytest.fixture
def docker_daemon_access(
    request: pytest.FixtureRequest,
    _xdist_docker_daemon_lock: ReaderWriterLock,
) -> Iterator[None]:
    """Coordinates access to the docker daemon shared by every xdist worker: tests take a
    "read" lock and run concurrently with each other; tests marked
    `@pytest.mark.docker_exclusive` take a "write" lock and run with NO other test holding
    this fixture concurrently in any worker.

    No-op when not running under xdist (single process cannot race itself): this also keeps
    non-xdist runs from attaching to - or being blocked by - lock marker files a crashed
    xdist session may have left behind in the shared base temp dir.
    """
    if not is_xdist_worker(request):
        yield
        return

    worker_id = get_worker_id(request)
    if worker_id not in _logged_activation:
        _logged_activation.add(worker_id)
        print(
            f"--> [{worker_id}] xdist_docker_daemon: locking shared docker daemon "
            "(read lock per test, write lock for @pytest.mark.docker_exclusive tests)"
        )

    token = f"{worker_id}-{uuid4().hex}"
    if request.node.get_closest_marker("docker_exclusive") is not None:
        with _xdist_docker_daemon_lock.write_lock(token=token, timeout=_EXCLUSIVE_LOCK_TIMEOUT):
            yield
    else:
        with _xdist_docker_daemon_lock.read_lock(token):
            yield


@pytest.fixture(autouse=True)
def _autouse_docker_daemon_access(docker_daemon_access: None) -> None:
    """Holds the daemon lock in EVERY test of a suite loading this plugin, so its xdist
    parallel speed-up stays race-free (see module docstring for why autouse is required).
    """
