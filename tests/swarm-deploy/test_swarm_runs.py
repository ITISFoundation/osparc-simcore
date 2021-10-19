# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import logging
import sys
import time
from pathlib import Path
from pprint import pformat
from typing import Any, Dict, List

import pytest
import requests
import tenacity
from docker import DockerClient
from docker.models.services import Service
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed
from yarl import URL

logger = logging.getLogger(__name__)

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


WAIT_TIME_SECS = 40
RETRY_COUNT = 7
MAX_WAIT_TIME = 240


# wait if running pre-state
# https://docs.docker.com/engine/swarm/how-swarm-mode-works/swarm-task-states/
SWARM_TASK_PRE_STATES = ["NEW", "PENDING", "ASSIGNED", "PREPARING", "STARTING"]

SWARM_TASK_FAILED_STATES = [
    "COMPLETE",
    "FAILED",
    "SHUTDOWN",
    "REJECTED",
    "ORPHANED",
    "REMOVE",
    "CREATED",
]


@pytest.fixture
def core_services_running(
    docker_client: DockerClient, core_stack_name: str
) -> List[Service]:
    # Matches service names in stacks as e.g.
    #
    #  'mystack_director'
    #  'mystack_postgres-exporter'
    #  'mystack_postgres_exporter'
    #
    # for a stack named 'mystack'

    # TODO: find a more reliable way to list services in a stack
    running_services = [
        service
        for service in docker_client.services.list()
        if service.name.startswith(core_stack_name)
    ]
    return running_services


def test_all_services_up(
    core_services_running: List[Service],
    core_stack_name: str,
    core_stack_compose: Dict[str, Any],
):
    running_services_names = set(service.name for service in core_services_running)

    expected_services_names = {
        f"{core_stack_name}_{service_name}"
        for service_name in core_stack_compose["services"].keys()
    }
    assert running_services_names == expected_services_names


@pytest.mark.skip(
    reason="this test is constantly failing because the postgres/migration is not available when other services are starting"
)
@pytest.mark.parametrize(
    "docker_compose_service_key",
    [
        "api-server",
        "catalog",
        "dask-scheduler",
        "dask-sidecar",
        "datcore-adapter",
        "director-v2",
        "director",
        "migration",
        "postgres",
        "rabbit",
        "redis",
        "static-webserver",
        "storage",
        "traefik",
        "webserver",
        "whoami",
    ],
)
def test_core_service_running(
    docker_compose_service_key: str,
    core_stack_name: str,
    core_services_running: List[Service],
    core_stack_compose: Dict[str, Any],
    docker_client: DockerClient,
):
    service_name = f"{core_stack_name}_{docker_compose_service_key}"
    service_config = core_stack_compose["services"][docker_compose_service_key]

    assert any(s.name == service_name for s in core_services_running)

    service: Service = next(s for s in core_services_running if s.name == service_name)

    # Every service in the fixture runs a number of tasks, but they might have failed!
    #
    # $ docker service ps simcore_storage
    # ID                  NAME                     IMAGE                     NODE                DESIRED STATE       CURRENT STATE            ERROR                       PORTS
    # puiaevvmtbs1        simcore_storage.1       simcore_storage:latest   crespo-wkstn        Running             Running 18 minutes ago
    # j5xtlrnn684y         \_ simcore_storage.1   simcore_storage:latest   crespo-wkstn        Shutdown            Failed 18 minutes ago    "task: non-zero exit (1)"
    tasks = service.tasks()
    num_tasks = get_replicas(service_config)

    assert len(tasks) == num_tasks, (
        f"Expected a {num_tasks} task(s) for '{service_name}', got instead"
        f"\n{ get_tasks_summary(tasks) }"
        f"\n{ get_failed_tasks_logs(service, docker_client) }"
    )

    for i in range(num_tasks):
        task: Dict[str, Any] = service.tasks()[i]

        for n in range(RETRY_COUNT):
            task = service.tasks()[i]

            if task["Status"]["State"].upper() in SWARM_TASK_PRE_STATES:
                print(
                    "Waiting [{}/{}] ...\n{}".format(
                        n, RETRY_COUNT, get_tasks_summary(tasks)
                    )
                )
                time.sleep(WAIT_TIME_SECS)
            else:
                break

        # should be running
        assert task["Status"]["State"].upper() == "RUNNING", (
            "Expected running, got instead"
            f"\n{pformat(task)}"
            f"\n{get_failed_tasks_logs(service, docker_client)}"
        )


@pytest.mark.parametrize(
    "test_url,expected_in_content",
    [
        ("http://127.0.0.1:9081/", "osparc/boot.js"),
        ("http://127.0.0.1:9081/s4l/index.html", "Sim4Life"),
        ("http://127.0.0.1:9081/tis/index.html", "TI Treatment Planning"),
    ],
)
def test_product_frontend_app_served(
    deployed_simcore_stack: List[Service],
    traefik_service: URL,
    test_url: str,
    expected_in_content: str,
    loop,
):
    # NOTE: it takes a bit of time until traefik sets up the correct proxy and
    # the webserver takes time to start
    # TODO: determine wait times with pre-calibration step
    @tenacity.retry(
        wait=wait_fixed(10),
        stop=stop_after_attempt(20),
    )
    def request_test_url():
        resp = requests.get(test_url)
        assert (
            resp.ok
        ), f"Failed request {resp.url} with {resp.status_code}: {resp.reason}"
        return resp

    resp = request_test_url()

    # TODO: serch osparc-simcore commit id e.g. 'osparc-simcore v817d82e'
    assert resp.ok
    assert "text/html" in resp.headers["Content-Type"]
    assert expected_in_content in resp.text, "Expected boot not found in response"


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
        msg += (
            "- task ID:{ID}, STATE: {Status[State]}, ERROR: '{Status[Err]}' \n".format(
                **t
            )
        )
    return msg


def get_failed_tasks_logs(service, docker_client):
    failed_logs = ""
    for t in service.tasks():
        if t["Status"]["State"].upper() in SWARM_TASK_FAILED_STATES:
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
