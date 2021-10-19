# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import logging
import subprocess
from datetime import datetime
from pprint import pformat
from typing import Any, Dict, List

import pytest
from docker import DockerClient
from docker.models.services import Service
from pytest_simcore.docker_swarm import by_task_update
from tenacity import Retrying
from tenacity.before import before_log
from tenacity.stop import stop_after_attempt
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


# CORE stack


@pytest.fixture(scope="module")
def core_services_selection(simcore_docker_compose: Dict) -> List[str]:
    ## OVERRIDES packages/pytest-simcore/src/pytest_simcore/docker_compose.py::core_services_selection
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


WAIT_TIME_BETWEEN_RETRIES_SECS = 30
NUMBER_OF_ATTEMPTS = 10


def to_datetime(datetime_str: str) -> datetime:
    # datetime_str is typically '2020-10-09T12:28:14.771034099Z'
    #  - The T separates the date portion from the time-of-day portion
    #  - The Z on the end means UTC, that is, an offset-from-UTC
    # The 099 before the Z is not clear, therefore we will truncate the last part
    N = len("2020-10-09T12:28:14.7710")
    if len(datetime_str) > N:
        datetime_str = datetime_str[:N]
    return datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%S.%f")


def by_task_update(task: Dict) -> datetime:
    datetime_str = task["Status"]["Timestamp"]
    return to_datetime(datetime_str)


@pytest.fixture(scope="module")
def deployed_simcore_stack(
    core_stack_name: str, core_stack_compose: Dict, docker_client: DockerClient
) -> List[Service]:

    # NOTE: the goal here is NOT to test time-to-deploy but
    # rather guaranteing that the framework is fully deployed before starting
    # tests. Obviously in a critical state in which the frameworks has a problem
    # the fixture will fail
    desired_state_to_state_map = {
        "shutdown": ["failed", "shutdown", "complete"],
        "running": ["running"],
    }
    try:
        for attempt in Retrying(
            wait=wait_fixed(WAIT_TIME_BETWEEN_RETRIES_SECS),
            stop=stop_after_attempt(NUMBER_OF_ATTEMPTS),
            before=before_log(log, logging.WARNING),
        ):
            with attempt:
                for service in docker_client.services.list():
                    print(f"Waiting for {service.name}...")
                    for task in sorted(service.tasks(), key=by_task_update):
                        # NOTE: Could have been restarted from latest test parameter, accept as well complete
                        assert (
                            task["Status"]["State"]
                            in desired_state_to_state_map[task["DesiredState"]]
                        ), (
                            f"{service.name} still not ready or complete. Expected "
                            f"desired_state[{task['DesiredState']}] but got "
                            f"status_state[{task['Status']['State']}]). Details:"
                            f"\n{pformat(task)}"
                        )

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
        for service in docker_client.services.list()
        if service.name.startswith(f"{core_stack_name}_")
    ]  # type: ignore

    assert (
        core_stack_services
    ), f"Expected some services in core stack '{core_stack_name}'"

    assert len(core_stack_compose["services"].keys()) == len(core_stack_services)

    return core_stack_services
