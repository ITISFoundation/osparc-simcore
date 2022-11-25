""" Free helper functions for docker API

"""

import asyncio
import collections
import logging
import re
from typing import Final

import aiodocker
from models_library.docker import DockerLabelKey
from models_library.generated_models.docker_rest_api import Node, Task, TaskState
from pydantic import ByteSize, parse_obj_as
from servicelib.logging_utils import log_context
from servicelib.utils import logged_gather
from tenacity import TryAgain, retry
from tenacity.after import after_log
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

from .models import Resources

logger = logging.getLogger(__name__)
_NANO_CPU: Final[float] = 10**9

_TASK_STATUS_WITH_ASSIGNED_RESOURCES: Final[tuple[TaskState, ...]] = (
    TaskState.assigned,
    TaskState.accepted,
    TaskState.preparing,
    TaskState.starting,
    TaskState.running,
)
_MINUTE: Final[int] = 60
_TIMEOUT_WAITING_FOR_NODES_S: Final[int] = 5 * _MINUTE


async def get_monitored_nodes(node_labels: list[DockerLabelKey]) -> list[Node]:
    async with aiodocker.Docker() as docker:
        nodes = parse_obj_as(
            list[Node],
            await docker.nodes.list(
                filters={"node.label": [f"{label}=true" for label in node_labels]}
            ),
        )
    return nodes


async def pending_service_tasks_with_insufficient_resources(
    service_labels: list[DockerLabelKey],
) -> list[Task]:
    """
    Returns the docker service tasks that are currently pending due to missing resources.

    Tasks pending with insufficient resources are
    - pending
    - have an error message with "insufficient resources"
    - are not scheduled on any node
    """
    async with aiodocker.Docker() as docker:
        tasks = parse_obj_as(
            list[Task],
            await docker.tasks.list(
                filters={
                    "desired-state": "running",
                    "label": service_labels,
                }
            ),
        )

    def _is_task_waiting_for_resources(task: Task) -> bool:
        # NOTE: https://docs.docker.com/engine/swarm/how-swarm-mode-works/swarm-task-states/
        if (
            not task.Status
            or not task.Status.State
            or not task.Status.Message
            or not task.Status.Err
        ):
            return False
        return (
            task.Status.State == TaskState.pending
            and task.Status.Message == "pending task scheduling"
            and "insufficient resources on" in task.Status.Err
        )

    pending_tasks = [task for task in tasks if _is_task_waiting_for_resources(task)]

    return pending_tasks


async def compute_cluster_total_resources(nodes: list[Node]) -> Resources:
    """
    Returns the nodes total resources.
    """
    cluster_resources_counter = collections.Counter({"ram": 0, "cpus": 0})
    for node in nodes:
        assert node.Description  # nosec
        assert node.Description.Resources  # nosec
        assert node.Description.Resources.NanoCPUs  # nosec
        cluster_resources_counter.update(
            {
                "ram": node.Description.Resources.MemoryBytes,
                "cpus": node.Description.Resources.NanoCPUs / _NANO_CPU,
            }
        )

    return Resources.parse_obj(dict(cluster_resources_counter))


def get_resources_from_docker_task(task: Task) -> Resources:
    assert task.Spec  # nosec
    if task.Spec.Resources and task.Spec.Resources.Reservations:
        return Resources(
            cpus=(task.Spec.Resources.Reservations.NanoCPUs or 0) / _NANO_CPU,
            ram=parse_obj_as(
                ByteSize, task.Spec.Resources.Reservations.MemoryBytes or 0
            ),
        )
    return Resources(cpus=0, ram=ByteSize(0))


async def compute_node_used_resources(node: Node) -> Resources:
    cluster_resources_counter = collections.Counter({"ram": 0, "cpus": 0})
    async with aiodocker.Docker() as docker:
        all_tasks_on_node = parse_obj_as(
            list[Task], await docker.tasks.list(filters={"node": node.ID})
        )
        for task in all_tasks_on_node:
            assert task.Status  # nosec
            if (
                task.Status.State in _TASK_STATUS_WITH_ASSIGNED_RESOURCES
                and task.Spec
                and task.Spec.Resources
                and task.Spec.Resources.Reservations
            ):
                task_reservations = task.Spec.Resources.Reservations.dict(
                    exclude_none=True
                )
                cluster_resources_counter.update(
                    {
                        "ram": task_reservations.get("MemoryBytes", 0),
                        "cpus": task_reservations.get("NanoCPUs", 0) / _NANO_CPU,
                    }
                )
    return Resources.parse_obj(dict(cluster_resources_counter))


async def compute_cluster_used_resources(nodes: list[Node]) -> Resources:
    """Returns the total amount of resources (reservations) used on each of the given nodes"""
    list_of_used_resources = await logged_gather(
        *(compute_node_used_resources(node) for node in nodes)
    )
    counter = collections.Counter({k: 0 for k in Resources.__fields__.keys()})
    for result in list_of_used_resources:
        counter.update(result.dict())

    return Resources.parse_obj(dict(counter))


_COMMAND_TIMEOUT_S = 10
_DOCKER_SWARM_JOIN_RE = r"(?P<command>docker swarm join)\s+(?P<token>--token\s+[\w-]+)\s+(?P<address>[0-9\.:]+)"
_DOCKER_SWARM_JOIN_PATTERN = re.compile(_DOCKER_SWARM_JOIN_RE)


async def get_docker_swarm_join_bash_command() -> str:
    """this assumes we are on a manager node"""
    command = ["docker", "swarm", "join-token", "worker"]
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    await asyncio.wait_for(process.wait(), timeout=_COMMAND_TIMEOUT_S)
    assert process.returncode is not None  # nosec
    if process.returncode > 0:
        raise RuntimeError(
            f"unexpected error running '{' '.join(command)}': {stderr.decode()}"
        )
    decoded_stdout = stdout.decode()
    if match := re.search(_DOCKER_SWARM_JOIN_PATTERN, decoded_stdout):
        capture = match.groupdict()
        return f"{capture['command']} --availability=drain {capture['token']} {capture['address']}"
    raise RuntimeError(
        f"expected docker '{_DOCKER_SWARM_JOIN_RE}' command not found: received {decoded_stdout}!"
    )


@retry(
    stop=stop_after_delay(_TIMEOUT_WAITING_FOR_NODES_S),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    after=after_log(logger, logging.ERROR),
    wait=wait_fixed(5),
)
async def wait_for_node(node_name: str) -> Node:
    async with aiodocker.Docker() as docker:
        list_of_nodes = await docker.nodes.list(filters={"name": node_name})
    if not list_of_nodes:
        raise TryAgain
    return parse_obj_as(Node, list_of_nodes[0])


async def tag_node(
    node: Node, *, tags: dict[DockerLabelKey, str], available: bool
) -> None:
    with log_context(
        logger, logging.DEBUG, msg=f"tagging {node.ID=} with {tags=} and {available=}"
    ):
        async with aiodocker.Docker() as docker:
            assert node.ID  # nosec
            assert node.Version  # nosec
            assert node.Version.Index  # nosec
            assert node.Spec  # nosec
            assert node.Spec.Role  # nosec
            await docker.nodes.update(
                node_id=node.ID,
                version=node.Version.Index,
                spec={
                    "Availability": "active" if available else "drain",
                    "Labels": tags,
                    "Role": node.Spec.Role.value,
                },
            )
