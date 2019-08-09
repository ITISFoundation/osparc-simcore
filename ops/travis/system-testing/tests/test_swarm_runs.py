# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
import datetime
import logging
import re
import sys
import urllib
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

# UTILS --------------------------------
def _here() -> Path:
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


def _load_yaml(path: Path) -> Dict:
    content = {}
    assert path.exists()
    with path.open() as f:
        content = yaml.safe_load(f)
    return content


def _services_docker_compose(osparc_simcore_root_dir: Path) -> Dict[str, str]:
    # TODO: pip install docker-compose and use
    # https://github.com/docker/compose/blob/master/compose/cli/main.py#L328
    osparc_simcore_services_dir = osparc_simcore_root_dir / "services"
    compose = {}
    for name in ["docker-compose.yml", ]:
        content = _load_yaml(osparc_simcore_services_dir / name)
        compose.update(content)
    return compose

def get_tasks_summary(tasks):
    msg = ""
    for t in tasks:
        t["Status"].setdefault("Err", '')
        msg += "- task ID:{ID}, STATE: {Status[State]}, ERROR: '{Status[Err]}' \n".format(
            **t)
    return msg


def get_failed_tasks_logs(service, docker_client):
    failed_states = ["COMPLETE", "FAILED",
                     "SHUTDOWN", "REJECTED", "ORPHANED", "REMOVE"]
    failed_logs = ""
    for t in service.tasks():
        if t['Status']['State'].upper() in failed_states:
            cid = t['Status']['ContainerStatus']['ContainerID']
            failed_logs += "{2} {0} - {1} BEGIN {2}\n".format(
                service.name, t['ID'], "="*10)
            if cid:
                container = docker_client.containers.get(cid)
                failed_logs += container.logs().decode('utf-8')
            else:
                failed_logs += "  log unavailable. container does not exists\n"
            failed_logs += "{2} {0} - {1} END {2}\n".format(
                service.name, t['ID'], "="*10)

    return failed_logs

# FIXTURES -------------------------------------
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

@pytest.fixture(scope='session')
def osparc_simcore_services_dir(osparc_simcore_root_dir) -> Path:
    services_dir = Path(osparc_simcore_root_dir) / "services"
    return services_dir

@pytest.fixture("session")
def services_docker_compose(osparc_simcore_root_dir) -> Dict[str, str]:
    return _services_docker_compose(osparc_simcore_root_dir)


@pytest.fixture("session")
def tools_docker_compose(osparc_simcore_root_dir) -> Dict[str, str]:
    content = _load_yaml(osparc_simcore_root_dir / "services" / "docker-compose-tools.yml")
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


# TESTS -------------------------------
def test_all_services_up(docker_client, services_docker_compose, tools_docker_compose):
    """
        NOTE: Assumes `make up-swarm` executed
    """
    running_services = docker_client.services.list()

    service_names = []
    service_names += services_docker_compose["services"]
    service_names += tools_docker_compose["services"]

    assert len(service_names) == len(running_services)

    for name in service_names:
        assert any( name in s.name for s in running_services ), f"{name} not in {running_services}"

async def test_core_service_running(core_service_name, docker_client, loop):
    """
        NOTE: Assumes `make up-swarm` executed
        NOTE: loop fixture makes this test async
    """
    SERVICE_NAMES_PATTERN = re.compile(r'([\w^_]+)_([-\w]+)')
    # Matches strings as
    # services_director
    # services_postgres-exporter
    # services_postgres_exporter

    # maps service names in docker-compose with actual services
    running_services = {}
    expected_prefix = None
    for service in docker_client.services.list():
        match = SERVICE_NAMES_PATTERN.match(service.name)
        assert match, f"Could not match service name {service.name}"
        prefix, service_name = match.groups()
        running_services[service_name] = service
        if expected_prefix:
            assert prefix == expected_prefix
        else:
            expected_prefix = prefix

    # find the service
    assert core_service_name in running_services
    running_service = running_services[core_service_name]

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


async def test_check_serve_root(docker_client, services_docker_compose, tools_docker_compose):
    """
        NOTE: Assumes `make up-swarm` executed
    """
    running_services = docker_client.services.list()
    assert (len(services_docker_compose["services"]) + len(tools_docker_compose["services"])) == len(running_services)

    req = urllib.request.Request("http://localhost:9081/")
    try:
        resp = urllib.request.urlopen(req)
        charset = resp.info().get_content_charset()
        content = resp.read().decode(charset)
        search = "osparc/boot.js"
        if content.find(search) < 0:
            pytest.fail("{} not found in main index.html".format(search))
    except urllib.error.HTTPError as err:
        pytest.fail("The server could not fulfill the request.\nError code {}".format(err.code))
    except urllib.error.URLError as err:
        pytest.fail("Failed reaching the server..\nError reason {}".format(err.reason))
