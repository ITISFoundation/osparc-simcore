# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import logging
import subprocess
from typing import Any, Dict, List, Literal, TypedDict

import pytest
from docker import DockerClient
from docker.models.services import Service
from pytest_simcore.docker_swarm import assert_service_is_running
from tenacity import Retrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

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

_MINUTE: int = 60  # secs


ServiceNameStr = str
ComposeSpec = Dict[str, Any]
UrlStr = str


class StackInfo(TypedDict):
    name: str
    compose: ComposeSpec


class DockerStackInfo(TypedDict):
    stacks: Dict[Literal["core", "ops"], StackInfo]
    services: List[ServiceNameStr]


# CORE stack -----------------------------------


@pytest.fixture(scope="module")
def core_services_selection(simcore_docker_compose: Dict) -> List[ServiceNameStr]:
    ## OVERRIDES packages/pytest-simcore/src/pytest_simcore/docker_compose.py::core_services_selection
    # select ALL services for these tests
    return list(simcore_docker_compose["services"].keys())


@pytest.fixture(scope="module")
def core_stack_name(docker_stack: DockerStackInfo) -> str:
    return docker_stack["stacks"]["core"]["name"]


@pytest.fixture(scope="module")
def core_stack_compose_specs(
    docker_stack: DockerStackInfo, simcore_docker_compose: Dict
) -> ComposeSpec:
    # verifies core_services_selection
    assert set(docker_stack["stacks"]["core"]["compose"]["services"]) == set(
        simcore_docker_compose["services"]
    )
    return docker_stack["stacks"]["core"]["compose"]


@pytest.fixture(scope="module")
def simcore_stack_deployed_services(
    docker_registry: UrlStr,
    core_stack_name: str,
    core_stack_compose_specs: ComposeSpec,
    docker_client: DockerClient,
) -> List[Service]:

    # NOTE: the goal here is NOT to test time-to-deploy but
    # rather guaranteing that the framework is fully deployed before starting
    # tests. Obviously in a critical state in which the frameworks has a problem
    # the fixture will fail
    try:
        for attempt in Retrying(
            wait=wait_fixed(5),
            stop=stop_after_delay(4 * _MINUTE),
            before_sleep=before_sleep_log(log, logging.INFO),
            reraise=True,
        ):
            with attempt:
                for service in docker_client.services.list():
                    assert_service_is_running(service)

    finally:
        subprocess.run(f"docker stack ps {core_stack_name}", shell=True, check=False)
        # logs table like
        #  ID                  NAME                  IMAGE                                      NODE                DESIRED STATE       CURRENT STATE                ERROR
        # xbrhmaygtb76        simcore_sidecar.1     itisfoundation/sidecar:latest              crespo-wkstn        Running             Running 53 seconds ago
        # zde7p8qdwk4j        simcore_rabbit.1      itisfoundation/rabbitmq:3.8.0-management   crespo-wkstn        Running             Running 59 seconds ago
        # f2gxmhwq7hhk        simcore_postgres.1    postgres:10.10                             crespo-wkstn        Running             Running about a minute ago
        # 1lh2hulxmc4q        simcore_director.1    itisfoundation/director:latest             crespo-wkstn        Running             Running 34 seconds ago
        # ...

    # TODO: find a more reliable way to list services in a stack
    core_stack_services: List[Service] = [
        service
        for service in docker_client.services.list(
            filters={"label": "{core_stack_name}_"}
        )
    ]  # type: ignore

    assert (
        core_stack_services
    ), f"Expected some services in core stack '{core_stack_name}'"

    assert len(core_stack_compose_specs["services"].keys()) == len(core_stack_services)

    return core_stack_services


# OPS stack -----------------------------------


@pytest.fixture(scope="module")
def ops_services_selection(ops_docker_compose: ComposeSpec) -> List[ServiceNameStr]:
    ## OVERRIDES packages/pytest-simcore/src/pytest_simcore/docker_compose.py::ops_services_selection
    # select ALL services for these tests
    return list(ops_docker_compose["services"].keys())


@pytest.fixture(scope="module")
def ops_stack_name(docker_stack: DockerStackInfo) -> str:
    return docker_stack["stacks"]["ops"]["name"]


@pytest.fixture(scope="module")
def ops_stack_compose_specs(
    docker_stack: DockerStackInfo, ops_docker_compose: ComposeSpec
) -> ComposeSpec:
    # verifies ops_services_selection
    assert set(docker_stack["stacks"]["ops"]["compose"]["services"]) == set(
        ops_docker_compose["services"]
    )
    return docker_stack["stacks"]["core"]["compose"]
