# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import sys
from pathlib import Path
from typing import Dict

import docker
import pytest
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


# the swarm should be up prior to testing... using make up-swarm

def test_services_running(docker_client, services_docker_compose, tools_docker_compose):
    running_services = docker_client.services.list()

    assert (len(services_docker_compose["services"]) + len(tools_docker_compose["services"])) == len(running_services)

    # all the services shall be available here
    for service_name in services_docker_compose["services"].keys():
        # find the service
        running_service = [x for x in running_services if service_name in x.name]
        assert len(running_service) == 1
        running_service = running_service[0]
        # check health
        task_infos = running_service.tasks()
        assert task_infos is not None

        status_json = task_infos[len(task_infos)-1]["Status"]
        task_state = status_json["State"]        
        assert task_state in ["running", "complete"], "service {} has state {}".format(service_name, task_state)
