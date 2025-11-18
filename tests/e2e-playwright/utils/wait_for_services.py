#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "aiodocker",
#     "aiofiles",
#     "arrow",
#     "pyyaml",
#     "rich",
#     "tenacity",
#     "typer",
# ]
# ///

import asyncio
import logging
import os
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import aiodocker
import arrow
import rich
import typer
import yaml
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

_logger = logging.getLogger(__name__)

_current_dir = (
    Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
)

WAIT_BEFORE_RETRY = 10
MAX_WAIT_TIME = 5 * 60

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


def get_tasks_summary(service_tasks: Sequence[dict[str, Any]]) -> str:
    msg = ""
    for task in service_tasks:
        status: dict[str, Any] = task["Status"]
        msg += f"- image: {task['Spec']['ContainerSpec']['Image']} task ID:{task['ID']}, CREATED: {task['CreatedAt']}, UPDATED: {task['UpdatedAt']}, DESIRED_STATE: {task['DesiredState']}, STATE: {status['State']}"
        error = status.get("Err")
        if error:
            msg += f", ERROR: {error}"
        msg += "\n"

    return msg


def osparc_simcore_root_dir() -> Path:
    WILDCARD = "services/web/server"

    root_dir = Path(_current_dir)
    while not any(root_dir.glob(WILDCARD)) and root_dir != Path("/"):
        root_dir = root_dir.parent

    msg = f"'{root_dir}' does not look like the git root directory of osparc-simcore"
    assert root_dir.exists(), msg
    assert any(root_dir.glob(WILDCARD)), msg
    assert any(root_dir.glob(".git")), msg

    return root_dir


def core_docker_compose_file() -> Path:
    stack_files = list(osparc_simcore_root_dir().glob(".stack-simcore*"))
    assert stack_files
    return stack_files[0]


def core_services() -> list[str]:
    with core_docker_compose_file().open() as fp:
        dc_specs = yaml.safe_load(fp)
        return list(dc_specs["services"].keys())


def ops_docker_compose_file() -> Path:
    return osparc_simcore_root_dir() / ".stack-ops.yml"


def ops_services() -> list[str]:
    with ops_docker_compose_file().open() as fp:
        dc_specs = yaml.safe_load(fp)
        return list(dc_specs["services"].keys())


def _by_service_creation(service: dict[str, Any]) -> datetime:
    datetime_str = service["CreatedAt"]

    return arrow.get(datetime_str).datetime


@retry(
    stop=stop_after_delay(MAX_WAIT_TIME),
    wait=wait_fixed(WAIT_BEFORE_RETRY),
    before_sleep=before_sleep_log(_logger, logging.WARNING),
)
async def _retrieve_started_services() -> list[dict[str, Any]]:
    expected_services = core_services() + ops_services()
    started_services: list[dict[str, Any]] = []
    async with aiodocker.Docker() as client:
        services_list = await client.services.list()

        started_services = sorted(
            (
                s
                for s in services_list
                if s["Spec"]["Name"].split("_")[-1] in expected_services
            ),
            key=_by_service_creation,
        )
        assert started_services, "no services started!"
        assert len(expected_services) == len(started_services), (
            "Some services are missing or unexpected:\n"
            f"expected: {len(expected_services)} {expected_services}\n"
            f"got: {len(started_services)} {[s['Spec']['Name'] for s in started_services]}"
        )
    return started_services


@retry(
    stop=stop_after_delay(MAX_WAIT_TIME),
    wait=wait_fixed(WAIT_BEFORE_RETRY),
    before_sleep=before_sleep_log(_logger, logging.WARNING),
)
async def _wait_for_service(service: dict[str, Any]) -> None:
    async with aiodocker.Docker() as client:
        expected_replicas = (
            service["Spec"]["Mode"]["Replicated"]["Replicas"]
            if "Replicated" in service["Spec"]["Mode"]
            else len(await client.nodes.list())  # we are in global mode
        )
        service_name = service["Spec"]["Name"]
        rich.print(
            f"Service: {service_name} expects {expected_replicas} replicas",
            "-" * 10,
        )
        # Get tasks for the service
        service_tasks: list[dict[str, Any]] = await client.tasks.list(
            filters={"service": service["Spec"]["Name"]}
        )
        rich.print(get_tasks_summary(service_tasks))

        #
        # NOTE: a service could set 'ready' as desired-state instead of 'running' if
        # it constantly breaks and the swarm decides to "stop trying".
        #
        valid_replicas = sum(
            task["Status"]["State"] == RUNNING_STATE for task in service_tasks
        )
        assert valid_replicas == expected_replicas


async def wait_for_services() -> int:
    started_services: list[dict[str, Any]] = await _retrieve_started_services()

    await asyncio.gather(*(_wait_for_service(service) for service in started_services))
    return os.EX_OK


def main() -> int:
    """Main entry point for the script."""
    return asyncio.run(wait_for_services())


if __name__ == "__main__":
    typer.run(main)
