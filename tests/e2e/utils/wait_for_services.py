import logging
from pdb import Pdb
import sys
import time
from pathlib import Path
from typing import List
from pprint import pformat

import docker
import yaml

logger = logging.getLogger(__name__)

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

WAIT_TIME_SECS = 20
RETRY_COUNT = 7
MAX_WAIT_TIME = 240

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
# UTILS --------------------------------


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
    # get all services
    services = core_services() + ops_services()

    client = docker.from_env()
    running_services = [
        x for x in client.services.list() if x.name.split("_")[-1] in services
    ]

    # check all services are in
    assert len(running_services), "no services started!"
    assert len(services) == len(
        running_services
    ), f"Some services are missing:\nexpected: {services}\ngot: {running_services}"
    # now check they are in running mode
    for service in running_services:
        task = None
        for n in range(RETRY_COUNT):
            # get last updated task
            sorted_tasks = sorted(service.tasks(), key=lambda task: task["UpdatedAt"])
            task = sorted_tasks[-1]

            if task["Status"]["State"].upper() in pre_states:
                print(
                    "Waiting [{}/{}] for {}...\n{}".format(
                        n, RETRY_COUNT, service.name, get_tasks_summary(service.tasks())
                    )
                )
                time.sleep(WAIT_TIME_SECS)
            elif task["Status"]["State"].upper() in failed_states:
                print(
                    f"Waiting [{n}/{RETRY_COUNT}] Service {service.name} failed once...\n{get_tasks_summary(service.tasks())}"
                )
                time.sleep(WAIT_TIME_SECS)
            else:
                break
        assert task
        assert (
            task["Status"]["State"].upper() == "RUNNING"
        ), "Expected running, got \n{}\n{}".format(
            pformat(task), get_tasks_summary(service.tasks())
        )
        # get_failed_tasks_logs(service, client))


if __name__ == "__main__":
    # get retry parameters
    # wait for the services
    sys.exit(wait_for_services())
