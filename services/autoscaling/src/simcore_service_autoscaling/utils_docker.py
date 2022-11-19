""" Free helper functions for docker API

"""

import collections
from typing import Final

import aiodocker
from models_library.generated_models.docker_rest_api import Node, Task, TaskState
from pydantic import parse_obj_as
from servicelib.utils import logged_gather

from .models import Resources

_NANO_CPU: Final[float] = 10**9

_TASK_STATUS_WITH_ASSIGNED_RESOURCES: Final[tuple[TaskState, ...]] = (
    TaskState.assigned,
    TaskState.accepted,
    TaskState.preparing,
    TaskState.starting,
    TaskState.running,
)


Label = str
NodeID = str


async def get_monitored_nodes(node_labels: list[Label]) -> list[Node]:
    async with aiodocker.Docker() as docker:
        nodes = parse_obj_as(
            list[Node],
            await docker.nodes.list(
                filters={"node.label": [f"{label}=true" for label in node_labels]}
            ),
        )
    return nodes


async def pending_service_tasks_with_insufficient_resources(
    service_labels: list[Label],
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
