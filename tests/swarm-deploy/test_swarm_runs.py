# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import logging
import os
import sys
import time
import urllib
from pathlib import Path
from pprint import pformat
from typing import Dict, List

import pytest
import tenacity
from docker import DockerClient
from docker.models.services import Service
from yarl import URL

logger = logging.getLogger(__name__)

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


WAIT_TIME_SECS = 20
RETRY_COUNT = 7
MAX_WAIT_TIME = 240


docker_compose_service_names = [
    "api-server",
    "catalog",
    "director",
    "migration",
    "sidecar",
    "storage",
    "webserver",
    "rabbit",
    "postgres",
    "redis",
    "traefik",
    "whoami",
]

stack_name = os.environ.get("SWARM_STACK_NAME", "simcore")

stack_service_names = sorted(
    [f"{stack_name}_{name}" for name in docker_compose_service_names]
)

# wait if running pre-state
# https://docs.docker.com/engine/swarm/how-swarm-mode-works/swarm-task-states/
pre_states = ["NEW", "PENDING", "ASSIGNED", "PREPARING", "STARTING"]

failed_states = [
    "COMPLETE",
    "FAILED",
    "SHUTDOWN",
    "REJECTED",
    "ORPHANED",
    "REMOVE",
    "CREATED",
]


@pytest.fixture(scope="session", params=stack_service_names)
def core_service_name(request) -> str:
    return str(request.param)


@pytest.fixture
def core_services_running(docker_client: DockerClient) -> List[Service]:
    # Matches service names in stacks as e.g.
    #
    #  'mystack_director'
    #  'mystack_postgres-exporter'
    #  'mystack_postgres_exporter'
    #
    # for a stack named 'mystack'

    # maps service names in docker-compose with actual services
    running_services = [
        s for s in docker_client.services.list() if s.name.startswith(stack_name)
    ]
    return running_services


def test_all_services_up(core_services_running: str, make_up_prod: Dict):
    running_services = sorted([s.name for s in core_services_running])
    assert running_services == stack_service_names

    expected = [
        f"{stack_name}_{service_name}"
        for service_name in make_up_prod[stack_name]["services"].keys()
    ]
    assert running_services == sorted(expected)


def test_core_service_running(
    core_service_name: str,
    core_services_running: List[Service],
    docker_client: DockerClient,
    make_up_prod: Dict,
):
    # find core_service_name
    running_service = next(
        s for s in core_services_running if s.name == core_service_name
    )

    # Every service in the fixture runs a number of tasks, but they might have failed!
    #
    # $ docker service ps simcore_storage
    # ID                  NAME                     IMAGE                     NODE                DESIRED STATE       CURRENT STATE            ERROR                       PORTS
    # puiaevvmtbs1        simcore_storage.1       simcore_storage:latest   crespo-wkstn        Running             Running 18 minutes ago
    # j5xtlrnn684y         \_ simcore_storage.1   simcore_storage:latest   crespo-wkstn        Shutdown            Failed 18 minutes ago    "task: non-zero exit (1)"
    tasks = running_service.tasks()
    service_config = make_up_prod["simcore"]["services"][
        core_service_name.split(sep="_")[1]
    ]
    num_tasks = get_replicas(service_config)
    assert len(tasks) == num_tasks, (
        f"Expected a {num_tasks} task(s) for '{0}',"
        " got:\n{1}\n{2}".format(
            core_service_name,
            get_tasks_summary(tasks),
            get_failed_tasks_logs(running_service, docker_client),
        )
    )

    for i in range(num_tasks):
        for n in range(RETRY_COUNT):
            task = running_service.tasks()[i]
            if task["Status"]["State"].upper() in pre_states:
                print(
                    "Waiting [{}/{}] ...\n{}".format(
                        n, RETRY_COUNT, get_tasks_summary(tasks)
                    )
                )
                time.sleep(WAIT_TIME_SECS)
            else:
                break

        # should be running
        assert (
            task["Status"]["State"].upper() == "RUNNING"
        ), "Expected running, got \n{}\n{}".format(
            pformat(task), get_failed_tasks_logs(running_service, docker_client)
        )


RETRY_WAIT_SECS = 2
RETRY_COUNT = 20


def test_check_serve_root(loop, make_up_prod: Dict, traefik_service: URL):

    req = urllib.request.Request("http://127.0.0.1:9081/")
    try:
        # it takes a bit of time until traefik sets up the correct proxy and the webserver takes time to start
        @tenacity.retry(
            wait=tenacity.wait_fixed(RETRY_WAIT_SECS),
            stop=tenacity.stop_after_attempt(RETRY_COUNT),
            before_sleep=tenacity.before_sleep_log(logger, logging.INFO),
        )
        def check_root(request):
            resp = urllib.request.urlopen(req)
            return resp

        resp = check_root(req)
        charset = resp.info().get_content_charset()
        content = resp.read().decode(charset)
        # TODO: serch osparc-simcore commit id e.g. 'osparc-simcore v817d82e'
        search = "osparc/boot.js"
        if content.find(search) < 0:
            pytest.fail("{} not found in main index.html".format(search))
    except urllib.error.HTTPError as err:
        pytest.fail(
            "The server could not fulfill the request.\nError code {}".format(err.code)
        )
    except urllib.error.URLError as err:
        pytest.fail("Failed reaching the server..\nError reason {}".format(err.reason))


# UTILS --------------------------------


def get_replicas(service: Dict) -> int:
    replicas = 1
    if "deploy" in service:
        if "replicas" in service["deploy"]:
            replicas = service["deploy"]["replicas"]
    return replicas


def get_tasks_summary(tasks):
    msg = ""
    for t in tasks:
        t["Status"].setdefault("Err", "")
        msg += "- task ID:{ID}, STATE: {Status[State]}, ERROR: '{Status[Err]}' \n".format(
            **t
        )
    return msg


def get_failed_tasks_logs(service, docker_client):
    failed_logs = ""
    for t in service.tasks():
        if t["Status"]["State"].upper() in failed_states:
            cid = t["Status"]["ContainerStatus"]["ContainerID"]
            failed_logs += "{2} {0} - {1} BEGIN {2}\n".format(
                service.name, t["ID"], "=" * 10
            )
            if cid:
                container = docker_client.containers.get(cid)
                failed_logs += container.logs().decode("utf-8")
            else:
                failed_logs += "  log unavailable. container does not exists\n"
            failed_logs += "{2} {0} - {1} END {2}\n".format(
                service.name, t["ID"], "=" * 10
            )

    return failed_logs
