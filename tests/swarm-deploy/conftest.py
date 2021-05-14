# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import logging
from typing import Any, Dict, List

import pytest

pytest_plugins = [
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_registry",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.minio_service",
    "pytest_simcore.postgres_service",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.repository_paths",
    "pytest_simcore.simcore_webserver_service",
    "pytest_simcore.tmp_path_extra",
    "pytest_simcore.traefik_service",
]
log = logging.getLogger(__name__)


# CORE stack


@pytest.fixture(scope="module")
def core_services_selection(simcore_docker_compose: Dict) -> List[str]:
    # select ALL services for these tests
    return list(simcore_docker_compose["services"].keys())


@pytest.fixture(scope="module")
def core_stack_name(docker_stack: Dict) -> str:
    return docker_stack["stacks"]["core"]["name"]


@pytest.fixture(scope="module")
def core_stack_compose(
    docker_stack: Dict, simcore_docker_compose: Dict
) -> Dict[str, Any]:
    # verifies core_services_selection
    assert set(docker_stack["stacks"]["core"]["compose"]["services"]) == set(
        simcore_docker_compose["services"]
    )
    return docker_stack["stacks"]["core"]["compose"]


# OPS stack


@pytest.fixture(scope="module")
def ops_services_selection(ops_docker_compose: Dict) -> List[str]:
    # select ALL services for these tests
    return list(ops_docker_compose["services"].keys())


@pytest.fixture(scope="module")
def ops_stack_name(docker_stack: Dict) -> str:
    return docker_stack["stacks"]["ops"]["name"]


@pytest.fixture(scope="module")
def ops_stack_compose(docker_stack: Dict, ops_docker_compose: Dict):
    # verifies ops_services_selection
    assert set(docker_stack["stacks"]["ops"]["compose"]["services"]) == set(
        ops_docker_compose["services"]
    )
    return docker_stack["stacks"]["core"]["compose"]
