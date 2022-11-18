""" Free helper functions for docker API

"""

import collections
from typing import Any, Final, Mapping

import aiodocker
from servicelib.utils import logged_gather

from .models import Resources

_NANO_CPU: Final[float] = 10**9

_TASK_STATUS_WITH_ASSIGNED_RESOURCES = [
    "assigned",
    "accepted",
    "preparing",
    "starting",
    "running",
]


Label = str
NodeID = str
Node = Mapping[str, Any]
Task = Mapping[str, Any]


async def get_monitored_nodes(node_labels: list[Label]) -> list[Node]:
    async with aiodocker.Docker() as docker:
        nodes = await docker.nodes.list(
            filters={"node.label": [f"{label}=true" for label in node_labels]}
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
    pending_tasks = []
    async with aiodocker.Docker() as docker:
        tasks = await docker.tasks.list(
            filters={
                "desired-state": "running",
                "label": service_labels,
            }
        )

        for task in tasks:
            if (
                task["Status"]["State"] == "pending"
                and task["Status"]["Message"] == "pending task scheduling"
                and "insufficient resources on" in task["Status"].get("Err", "no error")
            ):
                pending_tasks.append(task)
    return pending_tasks


async def compute_cluster_total_resources(nodes: list[Node]) -> Resources:
    """
    Returns the nodes total resources.
    """
    cluster_resources_counter = collections.Counter({"ram": 0, "cpus": 0})
    for node in nodes:
        cluster_resources_counter.update(
            {
                "ram": node["Description"]["Resources"]["MemoryBytes"],
                "cpus": node["Description"]["Resources"]["NanoCPUs"] / _NANO_CPU,
            }
        )

    return Resources.parse_obj(dict(cluster_resources_counter))


async def compute_node_used_resources(node: Node) -> Resources:
    cluster_resources_counter = collections.Counter({"ram": 0, "cpus": 0})
    async with aiodocker.Docker() as docker:
        all_tasks_on_node = await docker.tasks.list(filters={"node": node["ID"]})
        for task in all_tasks_on_node:
            if task["Status"]["State"] in _TASK_STATUS_WITH_ASSIGNED_RESOURCES:
                task_reservations = (
                    task["Spec"].get("Resources", {}).get("Reservations", {})
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
