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

logger = logging.getLogger(__name__)

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

WAIT_TIME_SECS = 20
RETRY_COUNT = 7
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


def get_tasks_summary(tasks):
    msg = ""
    for task in tasks:
        status: Dict = task["Status"]
        msg += f"- task ID:{task['ID']}, STATE: {status['State']}"
        error = status.get("Err")
        if error:
            msg += f", ERROR: {error}"
        msg += "\n"

    return msg


# --------------------------------------------------------------------------------


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


def wait_for_services() -> None:
    expected_services = core_services() + ops_services()

    client = docker.from_env()
    started_services = [
        s for s in client.services.list() if s.name.split("_")[-1] in expected_services
    ]

    assert len(started_services), "no services started!"
    assert len(expected_services) == len(started_services), (
        f"Some services are missing or unexpected:\n"
        "expected: {len(expected_services)} {expected_services}\n"
        "got: {len(started_services)} {[s.name for s in started_services]}"
    )
    # now check they are in running mode
    for service in started_services:

        # get last updated task

        def by_updated_timestamp(task) -> datetime:
            datetime_str = task["UpdatedAt"]
            # datetime_str is typically '2020-10-09T12:28:14.771034099Z'
            #  - The T separates the date portion from the time-of-day portion
            #  - The Z on the end means UTC, that is, an offset-from-UTC
            # The 099 before the Z is not clear, therefore we will truncate the last part
            N = len("2020-10-09T12:28:14.771034")
            if len(datetime_str) > N:
                datetime_str = datetime_str[:N]
            return datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%S.%f")

        task = sorted(service.tasks(), key=by_updated_timestamp)[-1]
        assert task

        # retry loop
        for n in range(RETRY_COUNT):
            if task["Status"]["State"] in PRE_STATES:
                print(
                    f"Waiting [{n}/{RETRY_COUNT}] for {service.name}...\n",
                    get_tasks_summary(service.tasks()),
                )
                time.sleep(WAIT_TIME_SECS)
            elif task["Status"]["State"] in FAILED_STATES:
                print(
                    f"Waiting [{n}/{RETRY_COUNT}] for {service.name} which failed ...\n",
                    get_tasks_summary(service.tasks()),
                )
                time.sleep(WAIT_TIME_SECS)
            else:
                break

        assert task["Status"]["State"] == task.get(
            "DesiredState", RUNNING_STATE
        ), f"Expected running, got \n{pformat(task)}\n" + get_tasks_summary(
            service.tasks()
        )


if __name__ == "__main__":
    sys.exit(wait_for_services())
