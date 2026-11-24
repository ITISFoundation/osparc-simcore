"""kind cluster lifecycle for the k8s flavor of the tests, analog to `docker_swarm`

The cluster is created with `make -C k8s create-cluster` when it does not exist. At session end it is
deleted with `make -C k8s delete-cluster` only when this session created it and
`--keep-docker-up` is not set. A cluster created outside pytest is never deleted.
"""

import logging
import subprocess
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Annotated, Final

import pytest
from annotated_types import doc

from .helpers.logging_tools import log_context

_logger: logging.Logger = logging.getLogger(__name__)

_K8S_MAKE_TIMEOUT: Final[timedelta] = timedelta(minutes=5)

_K8S_CLUSTER_CREATED_STASH_KEY: Final[
    Annotated[
        pytest.StashKey[Path],
        doc("k8s dir, set when this session created the cluster: only then sessionfinish deletes it"),
    ]
] = pytest.StashKey()


def _find_k8s_dir(start_dir: Path) -> Path:
    for directory in (start_dir, *start_dir.parents):
        if (directory / "k8s" / "Makefile").exists():
            return directory / "k8s"
    msg = f"no k8s/Makefile found in '{start_dir}' or its parents"
    raise FileNotFoundError(msg)


def _run_make(k8s_dir: Path, target: str, *make_vars: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    with log_context(logging.INFO, f"running 'make {target} {' '.join(make_vars)}' in {k8s_dir}", logger=_logger):
        return subprocess.run(  # noqa: S603
            ["make", "-C", f"{k8s_dir}", target, *make_vars],  # noqa: S607
            check=check,
            timeout=_K8S_MAKE_TIMEOUT.total_seconds(),
        )


def _k8s_cluster_exists(k8s_dir: Path) -> bool:
    return _run_make(k8s_dir, "cluster-exists", check=False).returncode == 0


@pytest.fixture(scope="session")
def k8s_dir(request: pytest.FixtureRequest) -> Path:
    return _find_k8s_dir(request.config.rootpath)


@pytest.fixture(scope="session")
def k8s_cluster(k8s_dir: Path, request: pytest.FixtureRequest) -> None:
    """ensures the kind cluster exists, creating it when it does not

    The cluster is deleted at session end (see `pytest_sessionfinish`), not in a fixture teardown,
    so that only a cluster this session created is deleted.
    """
    if not _k8s_cluster_exists(k8s_dir):
        _run_make(k8s_dir, "create-cluster")
        request.session.stash[_K8S_CLUSTER_CREATED_STASH_KEY] = k8s_dir


@pytest.fixture(scope="session")
def k8s_ops_workloads_selection() -> list[str]:
    """Names of the ops helm releases `k8s_ops_workloads` deploys. Override it in the test suite"""
    return []


@pytest.fixture(scope="session")
def k8s_ops_workloads(
    k8s_cluster: None, k8s_dir: Path, k8s_ops_workloads_selection: list[str], keep_docker_up: bool
) -> Iterator[list[str]]:
    """deploys the selected ops helm releases into the kind cluster and returns their names

    Releases are selected with helmfile's `--selector` (`RELEASE=<name>`); helmfile waits until
    each release is ready.
    """
    for release in k8s_ops_workloads_selection:
        _run_make(k8s_dir, "helmfile-ops-apply", f"RELEASE={release}")

    yield k8s_ops_workloads_selection

    if not keep_docker_up:
        for release in reversed(k8s_ops_workloads_selection):
            _run_make(k8s_dir, "helmfile-ops-destroy", f"RELEASE={release}")


def pytest_sessionfinish(session: pytest.Session) -> None:
    k8s_dir = session.stash.get(_K8S_CLUSTER_CREATED_STASH_KEY, None)
    if k8s_dir is None or session.config.getoption("--keep-docker-up", default=False):
        return
    _run_make(k8s_dir, "delete-cluster")
