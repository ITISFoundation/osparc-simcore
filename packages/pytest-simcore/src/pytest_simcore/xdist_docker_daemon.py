"""Cross-worker locking for a docker daemon shared by pytest-xdist workers.

Load it (`pytest_plugins = ["pytest_simcore.xdist_docker_daemon"]`) ONLY in suites running under xdist
against ONE shared docker stack: every test then holds the daemon lock, so tests marked
`docker_exclusive` (e.g. those listing ALL swarm services) never overlap tests of other workers.
"""

from collections.abc import Iterator
from datetime import timedelta
from typing import Final
from uuid import uuid4

import pytest

from .helpers.xdist import ReaderWriterLock, get_worker_id, get_xdist_root_tmp_path, is_xdist_worker

_DOCKER_DAEMON_LOCK_NAME: Final[str] = "docker_daemon"

# an exclusive test waits for the tests running in the other workers: must exceed the longest of them
_EXCLUSIVE_LOCK_TIMEOUT: timedelta = timedelta(minutes=15)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "docker_exclusive: this test needs exclusive access to the shared docker daemon "
        "(no other test using the docker_daemon_access fixture running concurrently in any xdist worker)",
    )


@pytest.fixture(scope="session")
def _xdist_docker_daemon_lock(tmp_path_factory: pytest.TempPathFactory) -> ReaderWriterLock:
    return ReaderWriterLock(get_xdist_root_tmp_path(tmp_path_factory), _DOCKER_DAEMON_LOCK_NAME)


@pytest.fixture
def docker_daemon_access(
    request: pytest.FixtureRequest,
    _xdist_docker_daemon_lock: ReaderWriterLock,
) -> Iterator[None]:
    """Takes a "read" lock (tests run concurrently) or, for `@pytest.mark.docker_exclusive`,
    a "write" lock (no other test holding this fixture runs in any worker).

    No-op outside xdist.
    """
    if not is_xdist_worker(request):
        yield
        return

    token = f"{get_worker_id(request)}-{uuid4().hex}"
    if request.node.get_closest_marker("docker_exclusive") is not None:
        with _xdist_docker_daemon_lock.write_lock(token=token, timeout=_EXCLUSIVE_LOCK_TIMEOUT):
            yield
    else:
        with _xdist_docker_daemon_lock.read_lock(token):
            yield


@pytest.fixture(autouse=True)
def _autouse_docker_daemon_access(docker_daemon_access: None) -> None:
    """Autouse on purpose: loading this plugin is the opt-in, so every test takes the lock."""
