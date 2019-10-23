"""
PRECONDITION:
    Assumes simcore stack is deployed, i.e. make ops_disabled=1 up-version

SEE before_script() in ci/travis/system-testing/swarm-deploy
"""

# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
import datetime
import logging
import os
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


docker_compose_service_names = [
    'apihub',
    'director',
    'sidecar',
    'storage',
    'webserver',
    'rabbit',
    'postgres'
]

stack_name = os.environ.get("SWARM_STACK_NAME", 'simcore')

stack_service_names = sorted([ f"{stack_name}_{name}" for name in docker_compose_service_names ])



# UTILS --------------------------------

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
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

def osparc_simcore_root_dir(here) -> Path:
    root_dir = here.parent.parent.resolve()
    assert root_dir.exists(), "Is this service within osparc-simcore repo?"
    assert any(root_dir.glob("services/web/server")), "%s not look like rootdir" % root_dir
    return root_dir

@pytest.fixture(scope='session')
def osparc_simcore_services_dir(osparc_simcore_root_dir) -> Path:
    services_dir = Path(osparc_simcore_root_dir) / "services"
    return services_dir

@pytest.fixture(scope="session", params=stack_service_names)
def core_service_name(request):
    return str(request.param)

@pytest.fixture(scope="function")
def docker_client():
    client = docker.from_env()
    yield client

@pytest.fixture(scope="function")
def core_services_running(docker_client):
    # Matches service names in stacks as e.g.
    #
    #  'mystack_director'
    #  'mystack_postgres-exporter'
    #  'mystack_postgres_exporter'
    #
    # for a stack named 'mystack'

    # maps service names in docker-compose with actual services
    running_services = [ s for s in docker_client.services.list() if s.name.startswith(stack_name) ]
    return running_services

# TESTS -------------------------------
def test_all_services_up(core_services_running):
    running_services = sorted( [s.name for s in core_services_running] )
    assert  running_services == stack_service_names


async def test_core_service_running(core_service_name, core_services_running, docker_client, loop):
    """
        NOTE: loop fixture makes this test async
    """
    # find core_service_name
    running_service = next( s for s in core_services_running  if s.name == core_service_name )

    # Every service in the fixture runs a single task, but they might have failed!
    #
    # $ docker service ps simcore_storage
    # ID                  NAME                     IMAGE                     NODE                DESIRED STATE       CURRENT STATE            ERROR                       PORTS
    # puiaevvmtbs1        simcore_storage.1       simcore_storage:latest   crespo-wkstn        Running             Running 18 minutes ago
    # j5xtlrnn684y         \_ simcore_storage.1   simcore_storage:latest   crespo-wkstn        Shutdown            Failed 18 minutes ago    "task: non-zero exit (1)"
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


async def test_check_serve_root():
    # TODO: this is
    req = urllib.request.Request("http://127.0.0.1:9081/")
    try:
        resp = urllib.request.urlopen(req)
        charset = resp.info().get_content_charset()
        content = resp.read().decode(charset)
        # TODO: serch osparc-simcore commit id e.g. 'osparc-simcore v817d82e'
        search = "osparc/boot.js"
        if content.find(search) < 0:
            pytest.fail("{} not found in main index.html".format(search))
    except urllib.error.HTTPError as err:
        pytest.fail("The server could not fulfill the request.\nError code {}".format(err.code))
    except urllib.error.URLError as err:
        pytest.fail("Failed reaching the server..\nError reason {}".format(err.reason))
