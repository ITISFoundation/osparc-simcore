# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import datetime
import sys
from pathlib import Path
from typing import Dict

import docker
import pytest
import tenacity
import yaml


@pytest.fixture(scope="session")
def here() -> Path:
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture(scope='session')
def osparc_simcore_root_dir(here) -> Path:
    root_dir = here.parent.parent.parent.parent.resolve()
    assert root_dir.exists(), "Is this service within osparc-simcore repo?"
    assert any(root_dir.glob("services/web/server")), "%s not look like rootdir" % root_dir
    return root_dir

@pytest.fixture("session")
def services_docker_compose(osparc_simcore_root_dir) -> Dict[str, str]:
    docker_compose_path = osparc_simcore_root_dir / "services" / "docker-compose.yml"
    assert docker_compose_path.exists()

    content = {}
    with docker_compose_path.open() as f:
        content = yaml.safe_load(f)
    return content

@pytest.fixture("session")
def tools_docker_compose(osparc_simcore_root_dir) -> Dict[str, str]:
    docker_compose_path = osparc_simcore_root_dir / "services" / "docker-compose.tools.yml"
    assert docker_compose_path.exists()

    content = {}
    with docker_compose_path.open() as f:
        content = yaml.safe_load(f)
    return content


@pytest.fixture(scope="function")
def docker_client():
    client = docker.from_env()
    yield client

@tenacity.retry(stop=tenacity.stop_after_delay(240),
                wait=tenacity.wait_fixed(5),
                retry=tenacity.retry_if_exception_type(AssertionError))
def try_checking_task_state(running_service, service_name):
    tasks = running_service.tasks()
    assert tasks is not None
    task_info = tasks[len(tasks)-1]

    task_state = task_info["Status"]["State"]
    if task_state not in  ["running", "complete"]:
        # check if it is a ever restarting project
        assert len(tasks) > 1, "service {} has state {}".format(service_name, task_state)
        previous_task_state = tasks[len(tasks) - 1]["Status"]["State"]
        assert previous_task_state == "complete", "service {} has state {}".format(service_name, task_state)

    # also check it's running since at least 5sec
    creation_time = datetime.datetime.strptime(task_info["CreatedAt"].split(".")[0], "%Y-%m-%dT%H:%M:%S")
    now = datetime.datetime.now()
    difference = now - creation_time
    assert difference.total_seconds() > 5


def test_services_running(docker_client, services_docker_compose, tools_docker_compose):
    """
    the swarm should be up prior to testing... using make up-swarm

    """
    running_services = docker_client.services.list()

    assert (len(services_docker_compose["services"]) + len(tools_docker_compose["services"])) == len(running_services)

    # all the services shall be available here
    for service_name in services_docker_compose["services"].keys():
        # find the service
        running_service = [s for s in running_services if service_name in s.name]
        assert len(running_service) == 1
        running_service = running_service[0]
        # check health
        try_checking_task_state(running_service, service_name)
