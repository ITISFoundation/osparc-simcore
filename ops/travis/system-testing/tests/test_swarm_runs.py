# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
import datetime
import logging
import sys
from pathlib import Path
from pprint import pformat
from typing import Dict

import docker
import pytest
import tenacity
import yaml

logger = logging.getLogger(__name__)

WAIT_TIME_SECS = 20
RETRY_COUNT = 7
MAX_WAIT_TIME=240

logger = logging.getLogger(__name__)

def _here() -> Path:
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

@pytest.fixture(scope="session")
def here() -> Path:
    return _here()

def _osparc_simcore_root_dir(here) -> Path:
    root_dir = here.parent.parent.parent.parent.resolve()
    assert root_dir.exists(), "Is this service within osparc-simcore repo?"
    assert any(root_dir.glob("services/web/server")), "%s not look like rootdir" % root_dir
    return root_dir

@pytest.fixture(scope='session')
def osparc_simcore_root_dir(here) -> Path:
    return _osparc_simcore_root_dir(here)


def _services_docker_compose(osparc_simcore_root_dir) -> Dict[str, str]:
    docker_compose_path = osparc_simcore_root_dir / "services" / "docker-compose.yml"
    assert docker_compose_path.exists()

    content = {}
    with docker_compose_path.open() as f:
        content = yaml.safe_load(f)
    return content

@pytest.fixture("session")
def services_docker_compose(osparc_simcore_root_dir) -> Dict[str, str]:
    return _services_docker_compose(osparc_simcore_root_dir)


@pytest.fixture("session")
def tools_docker_compose(osparc_simcore_root_dir) -> Dict[str, str]:
    docker_compose_path = osparc_simcore_root_dir / "services" / "docker-compose.tools.yml"
    assert docker_compose_path.exists()

    content = {}
    with docker_compose_path.open() as f:
        content = yaml.safe_load(f)
    return content

def _list_core_services():
    exclude = ["webclient"]
    content = _services_docker_compose(_osparc_simcore_root_dir(_here()))
    return [name for name in content["services"].keys() if name not in exclude]

@pytest.fixture(scope="session",
                params=_list_core_services())
def core_service_name(request, services_docker_compose):
    return str(request.param)


@pytest.fixture(scope="function")
def docker_client():
    client = docker.from_env()
    yield client


# UTILS --------------------------------

def get_tasks_summary(tasks):
    msg = ""
    for t in tasks:
        t["Status"].setdefault("Err", '')
        msg += "- task ID:{ID}, STATE: {Status[State]}, ERROR: '{Status[Err]}' \n".format(**t)
    return msg

def get_failed_tasks_logs(service, docker_client):
    failed_states = ["COMPLETE", "FAILED", "SHUTDOWN", "REJECTED", "ORPHANED", "REMOVE"]
    failed_logs = ""
    for t in service.tasks():
        if t['Status']['State'].upper() in failed_states:
            cid = t['Status']['ContainerStatus']['ContainerID']
            failed_logs += "{2} {0} - {1} BEGIN {2}\n".format(service.name, t['ID'], "="*10)
            if cid:
                container = docker_client.containers.get(cid)
                failed_logs += container.logs().decode('utf-8')
            else:
                failed_logs += "  log unavailable. container does not exists\n"
            failed_logs += "{2} {0} - {1} END {2}\n".format(service.name, t['ID'], "="*10)

    return failed_logs

# TESTS -------------------------------

def test_all_services_up(docker_client, services_docker_compose, tools_docker_compose):
    """
        NOTE: Assumes `make up-swarm` executed
    """
    running_services = docker_client.services.list()

    assert (len(services_docker_compose["services"]) + len(tools_docker_compose["services"])) == len(running_services)

    # TODO: check names instead


async def test_core_service_running(core_service_name, docker_client, loop):
    """
        NOTE: Assumes `make up-swarm` executed
        NOTE: loop fixture makes this test async
    """
    running_services = docker_client.services.list()

    # find the service
    running_service = [s for s in running_services if core_service_name in s.name]
    assert len(running_service) == 1

    running_service = running_service[0]

    # Every service in the fixture runs a single task, but they might have failed!
    #
    # $ docker service ps services_storage
    # ID                  NAME                     IMAGE                     NODE                DESIRED STATE       CURRENT STATE            ERROR                       PORTS
    # puiaevvmtbs1        services_storage.1       services_storage:latest   crespo-wkstn        Running             Running 18 minutes ago
    # j5xtlrnn684y         \_ services_storage.1   services_storage:latest   crespo-wkstn        Shutdown            Failed 18 minutes ago    "task: non-zero exit (1)"
    tasks = running_service.tasks()

    assert len(tasks) == 1, "Expected a single task for '{0}',"\
        " got:\n{1}\n{2}".format(core_service_name,
                                 get_tasks_summary(tasks),
                                 get_failed_tasks_logs(running_service, docker_client))

    # wait if running pre-state
    # https://docs.docker.com/engine/swarm/how-swarm-mode-works/swarm-task-states/
    pre_states = ["NEW", "PENDING", "ASSIGNED", "PREPARING", "STARTING"]

    for n in range(RETRY_COUNT):
        task = running_service.tasks()[0]
        if task['Status']['State'].upper() in pre_states:
            print("Waiting [{}/{}] ...\n{}".format(n, RETRY_COUNT, get_tasks_summary(tasks)))
            await asyncio.sleep(WAIT_TIME_SECS)
        else:
            break

    # should be running
    assert task['Status']['State'].upper() == "RUNNING", \
        "Expected running, got \n{}\n{}".format(
                pformat(task),
                get_failed_tasks_logs(running_service, docker_client))
