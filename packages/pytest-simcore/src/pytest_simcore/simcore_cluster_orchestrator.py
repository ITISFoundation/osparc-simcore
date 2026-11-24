import os
from enum import StrEnum

import pytest


class SimcoreClusterOrchestrator(StrEnum):
    DOCKER_SWARM = "docker_swarm"
    K8S = "k8s"


def pytest_addoption(parser: pytest.Parser):
    simcore_group = parser.getgroup("simcore")
    simcore_group.addoption(
        "--simcore-cluster-orchestrator",
        action="store",
        choices=[o.value for o in SimcoreClusterOrchestrator],
        default=os.environ.get("SIMCORE_CLUSTER_ORCHESTRATOR", SimcoreClusterOrchestrator.DOCKER_SWARM),
        help="Cluster orchestrator the tests run against [env: SIMCORE_CLUSTER_ORCHESTRATOR, default: docker_swarm]",
    )


@pytest.fixture(scope="session")
def simcore_cluster_orchestrator(request: pytest.FixtureRequest) -> SimcoreClusterOrchestrator:
    return SimcoreClusterOrchestrator(request.config.getoption("--simcore-cluster-orchestrator"))
