# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import logging
import sys
from pathlib import Path
from typing import Dict

import pytest

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

pytest_plugins = [
    "pytest_simcore.environs",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.docker_registry",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.postgres_service",
    "pytest_simcore.minio_service",
    "pytest_simcore.traefik_service",
    "pytest_simcore.simcore_webserver_service",
]
log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def prepare_all_services(
    simcore_docker_compose: Dict, ops_docker_compose: Dict, request
) -> Dict:
    services = []
    for service in simcore_docker_compose["services"].keys():
        services.append(service)
    setattr(request.module, "core_services", services)
    core_services = getattr(request.module, "core_services", [])

    services = []
    for service in ops_docker_compose["services"].keys():
        services.append(service)
    setattr(request.module, "ops_services", services)
    ops_services = getattr(request.module, "ops_services", [])

    services = {"simcore": simcore_docker_compose, "ops": ops_docker_compose}
    return services



@pytest.fixture(scope="module")
def make_up_prod(
    prepare_all_services: Dict,
    simcore_docker_compose: Dict,
    ops_docker_compose: Dict,
    docker_stack: Dict,
) -> Dict:
    stack_configs = {"simcore": simcore_docker_compose, "ops": ops_docker_compose}
    return stack_configs
