import logging
import subprocess
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Final

import pytest
from annotated_types import doc

from .helpers import FIXTURE_CONFIG_CORE_SERVICES_SELECTION, FIXTURE_CONFIG_OPS_SERVICES_SELECTION
from .helpers.constants import HEADER_STR
from .helpers.logging_tools import log_context
from .helpers.monkeypatch_envs import load_dotenv
from .helpers.typing_env import FrozenEnvVarsDict

_logger: logging.Logger = logging.getLogger(__name__)

_K8S_MAKE_TIMEOUT: Final[timedelta] = timedelta(minutes=5)

_K8S_CLUSTER_CREATED_STASH_KEY: Final[
    Annotated[
        pytest.StashKey[Path],
        doc("k8s dir, set when this session created the cluster: only then sessionfinish deletes it"),
    ]
] = pytest.StashKey()


def _run_make(k8s_dir: Path, target: str, *make_vars: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    cmd: list[str] = ["make", "-C", f"{k8s_dir}", target, *make_vars]
    with log_context(logging.INFO, f"running '{' '.join(cmd)}'", logger=_logger):
        try:
            return subprocess.run(  # noqa: S603
                cmd,
                check=check,
                capture_output=True,
                timeout=_K8S_MAKE_TIMEOUT.total_seconds(),
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as err:
            msg = (
                f"'{' '.join(cmd)}' failed: {err}\n"
                f"{HEADER_STR.format('stdout')}{(err.stdout or b'').decode('utf8', 'replace')}\n"
                f"{HEADER_STR.format('stderr')}{(err.stderr or b'').decode('utf8', 'replace')}"
            )
            raise RuntimeError(msg) from err


def _k8s_cluster_exists(k8s_dir: Path) -> bool:
    return _run_make(k8s_dir, "cluster-exists", check=False).returncode == 0


@pytest.fixture(scope="session")
def kubernetes_cluster_env(kind_env_file: Path) -> FrozenEnvVarsDict:
    """Host address and ports where the kind cluster publishes its workloads (k8s/kind.env)"""
    return MappingProxyType(load_dotenv(kind_env_file, verbose=True, interpolate=True))


@pytest.fixture(scope="session")
def k8s_cluster(osparc_simcore_k8s_dir: Path, request: pytest.FixtureRequest) -> None:
    if not _k8s_cluster_exists(osparc_simcore_k8s_dir):
        _run_make(osparc_simcore_k8s_dir, "create-cluster")
        request.session.stash[_K8S_CLUSTER_CREATED_STASH_KEY] = osparc_simcore_k8s_dir


@contextmanager
def deployed_ops_workloads(k8s_dir: Path, selection: list[str], keep_up: bool) -> Generator[list[str]]:
    for release in selection:
        _run_make(k8s_dir, "helmfile-ops-apply", f"RELEASE={release}")

    yield selection

    if not keep_up:
        for release in reversed(selection):
            _run_make(k8s_dir, "helmfile-ops-destroy", f"RELEASE={release}")


@pytest.fixture(scope="module")
def k8s_ops_workloads(
    k8s_cluster: None,
    osparc_simcore_k8s_dir: Path,
    keep_docker_up: bool,
    request: pytest.FixtureRequest,
) -> Iterator[list[str]]:
    services = [
        *getattr(request.module, FIXTURE_CONFIG_CORE_SERVICES_SELECTION, []),
        *getattr(request.module, FIXTURE_CONFIG_OPS_SERVICES_SELECTION, []),
    ]
    with deployed_ops_workloads(osparc_simcore_k8s_dir, services, keep_docker_up) as releases:
        yield releases


def pytest_sessionfinish(session: pytest.Session) -> None:
    k8s_dir = session.stash.get(_K8S_CLUSTER_CREATED_STASH_KEY, None)
    if k8s_dir is None or session.config.getoption("--keep-docker-up", default=False):
        return
    _run_make(k8s_dir, "delete-cluster")
