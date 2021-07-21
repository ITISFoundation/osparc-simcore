# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import logging
import sys
import time
from collections import deque
from pathlib import Path
from pprint import pformat
from typing import Any, Deque, Dict, List, Set

import pytest
import requests
import tenacity
from docker import DockerClient
from docker.models.services import Service
from yarl import URL

logger = logging.getLogger(__name__)

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

SEPARATOR_LINE = "-" * 50

WAIT_TIME_SECS = 40
RETRY_COUNT = 7
MAX_WAIT_TIME = 240


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
        "sidecar",
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

    expected_replicas = get_replicas(service_config)

    # assert number of slots equals number of expected services
    tasks = service.tasks()
    slots: Set[int] = {t["Slot"] for t in tasks}
    slot_count = len(slots)

    assert slot_count == expected_replicas, (
        f"Expected to have {expected_replicas} slot(s), "
        f"instead {slot_count} slot(s) were found."
        f"\n{get_tasks_summary(tasks)}"
        f"\n{get_failed_tasks_logs(service, docker_client)}"
    )

    def _get_tasks_by_slots() -> Dict[int, Deque[Dict[str, Any]]]:
        results: Dict[int, Deque[Dict[str, Any]]] = {}

        for task in service.tasks():
            slot = task["Slot"]
            if slot not in results:
                results[slot] = deque()
            results[slot].append(task)

        return results

    def _are_any_tasks_running(slot_tasks: Deque[Dict[str, Any]]) -> bool:
        running_tasks = [
            t for t in slot_tasks if t["Status"]["State"].upper() == "RUNNING"
        ]
        return len(running_tasks) > 0

    # check at least one service in per slot is in running mode else raise error
    tasks_by_slot: Dict[int, Deque[Dict[str, Any]]] = {}
    running_service_by_slot: Dict[int, bool] = {s: False for s in slots}
    for _ in range(RETRY_COUNT):
        tasks_by_slot = _get_tasks_by_slots()
        assert len(tasks_by_slot) == expected_replicas

        for slot, slot_tasks in tasks_by_slot.items():
            if _are_any_tasks_running(slot_tasks):
                running_service_by_slot[slot] = True

        # if all services for all states are running then
        if all(running_service_by_slot.values()):
            break
        else:
            time.sleep(WAIT_TIME_SECS)

    # expecting no error, otherwise a nice error message is welcomed
    error_message = ""
    for slot, slot_tasks in tasks_by_slot.items():
        if not _are_any_tasks_running(slot_tasks):
            message = (
                f"Expected running service for slot {slot}, "
                f"but got instead\n{SEPARATOR_LINE}"
            )
            for task in slot_tasks:
                message += (
                    f"\n{get_task_logs(task, service.name, docker_client)}"
                    f"\n{pformat(task)}"
                    f"\n{get_task_logs(task, service.name, docker_client)}"
                    f"\n{SEPARATOR_LINE}"
                )
                error_message += f"{message}\n"

    assert error_message == ""


@pytest.mark.parametrize(
    "test_url,expected_in_content",
    [
        ("http://127.0.0.1:9081/", "osparc/boot.js"),
        ("http://127.0.0.1:9081/s4l/index.html", "Sim4Life"),
        ("http://127.0.0.1:9081/tis/index.html", "TI Treatment Planning"),
    ],
)
def test_product_frontend_app_served(
    traefik_service: URL,
    test_url: str,
    expected_in_content: str,
    loop,
):
    # NOTE: it takes a bit of time until traefik sets up the correct proxy and
    # the webserver takes time to start
    # TODO: determine wait times with pre-calibration step
    @tenacity.retry(
        wait=tenacity.wait_fixed(2),
        stop=tenacity.stop_after_attempt(20),
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


def get_task_logs(task, service_name, docker_client):
    task_logs = ""

    cid = task["Status"]["ContainerStatus"]["ContainerID"]
    task_logs += "{2} {0} - {1} BEGIN {2}\n".format(service_name, task["ID"], "=" * 10)
    if cid:
        container = docker_client.containers.get(cid)
        task_logs += container.logs().decode("utf-8")
    else:
        task_logs += "  log unavailable. container does not exists\n"
    task_logs += "{2} {0} - {1} END {2}\n".format(service_name, task["ID"], "=" * 10)

    return task_logs


def get_failed_tasks_logs(service, docker_client):
    failed_logs = ""

    for t in service.tasks():
        if t["Status"]["State"].upper() in SWARM_TASK_FAILED_STATES:
            failed_logs += get_task_logs(t, service.name, docker_client)

    return failed_logs
