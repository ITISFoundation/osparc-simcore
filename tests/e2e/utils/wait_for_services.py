import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from pdb import Pdb
from pprint import pformat
from typing import Dict, List

import docker
import yaml
from tenacity import Retrying, before_sleep_log, stop_after_attempt, wait_fixed

logger = logging.getLogger(__name__)

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

WAIT_BEFORE_RETRY = 5
MAX_RETRY_COUNT = 7
MAX_WAIT_TIME = 240

# SEE https://docs.docker.com/engine/swarm/how-swarm-mode-works/swarm-task-states/

PRE_STATES = [
    "new",  # The task was initialized.
    "pending",  # Resources for the task were allocated.
    "assigned",  # Docker assigned the task to nodes.
    "accepted",  # The task was accepted by a worker node. If a worker node rejects the task, the state changes to REJECTED.
    "preparing",  # Docker is preparing the task.
    "starting",  # Docker is starting the task.
]

RUNNING_STATE = "running"  # The task is executing.

FAILED_STATES = [
    "complete",  # The task exited without an error code.
    "failed",  # The task exited with an error code.
    "shutdown",  # Docker requested the task to shut down.
    "rejected",  # The worker node rejected the task.
    "orphaned",  # The node was down for too long.
    "remove",  # The task is not terminal but the associated service was removed or scaled down.
]


def get_tasks_summary(service_tasks):
    msg = ""
    for task in service_tasks:
        status: Dict = task["Status"]
        msg += f"- task ID:{task['ID']}, , CREATED: {task['CreatedAt']}, UPDATED: {task['UpdatedAt']}, STATE: {status['State']}"
        error = status.get("Err")
        if error:
            msg += f", ERROR: {error}"
        msg += "\n"

    return msg


def osparc_simcore_root_dir() -> Path:
    WILDCARD = "services/web/server"

    root_dir = Path(current_dir)
    while not any(root_dir.glob(WILDCARD)) and root_dir != Path("/"):
        root_dir = root_dir.parent

    msg = f"'{root_dir}' does not look like the git root directory of osparc-simcore"
    assert root_dir.exists(), msg
    assert any(root_dir.glob(WILDCARD)), msg
    assert any(root_dir.glob(".git")), msg

    return root_dir


def core_docker_compose_file() -> Path:
    return osparc_simcore_root_dir() / ".stack-simcore-version.yml"


def core_services() -> List[str]:
    with core_docker_compose_file().open() as fp:
        dc_specs = yaml.safe_load(fp)
        return [x for x in dc_specs["services"].keys()]


def ops_docker_compose_file() -> Path:
    return osparc_simcore_root_dir() / ".stack-ops.yml"


def ops_services() -> List[str]:
    with ops_docker_compose_file().open() as fp:
        dc_specs = yaml.safe_load(fp)
        return [x for x in dc_specs["services"].keys()]


def to_datetime(datetime_str: str) -> datetime:
    # datetime_str is typically '2020-10-09T12:28:14.771034099Z'
    #  - The T separates the date portion from the time-of-day portion
    #  - The Z on the end means UTC, that is, an offset-from-UTC
    # The 099 before the Z is not clear, therefore we will truncate the last part
    N = len("2020-10-09T12:28:14.771034")
    if len(datetime_str) > N:
        datetime_str = datetime_str[:N]
    return datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%S.%f")


def by_service_creation(service):
    datetime_str = service.attrs["CreatedAt"]
    return to_datetime(datetime_str)


def wait_for_services() -> None:
    expected_services = core_services() + ops_services()

    client = docker.from_env()
    started_services = sorted(
        [
            s
            for s in client.services.list()
            if s.name.split("_")[-1] in expected_services
        ],
        key=by_service_creation,
    )

    assert len(started_services), "no services started!"
    assert len(expected_services) == len(started_services), (
        f"Some services are missing or unexpected:\n"
        "expected: {len(expected_services)} {expected_services}\n"
        "got: {len(started_services)} {[s.name for s in started_services]}"
    )

    for service in started_services:

        expected_replicas = service.attrs["Spec"]["Mode"]["Replicated"]["Replicas"]
        print(f"Service: {service.name} expects {expected_replicas} replicas", "-"*10)

        for attempt in Retrying(
            stop=stop_after_attempt(MAX_RETRY_COUNT),
            wait=wait_fixed(WAIT_BEFORE_RETRY),
            reraise=True,
            before_sleep=before_sleep_log(logger, logging.WARNING),
        ):
            with attempt:
                service_tasks: List[Dict] = service.tasks()  #  freeze
                print(get_tasks_summary(service_tasks))

                #
                # NOTE: a service could set 'ready' as desired-state instead of 'running' if
                # it constantly breaks and the swarm desides to "stopy trying".
                #
                valid_replicas = sum(
                    task.get("DesiredState") == task["Status"]["State"]
                    for task in service_tasks
                )
                assert (
                    valid_replicas == expected_replicas
                ), f"Service {service.name} failed to start"


if __name__ == "__main__":
    sys.exit(wait_for_services())
