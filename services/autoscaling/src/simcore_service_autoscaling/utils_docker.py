""" Free helper functions for docker API

"""

import collections
from typing import Any, Final, Mapping

import aiodocker
from pydantic import BaseModel, ByteSize

_NANO_CPU: Final[float] = 10**9

_TASK_STATUS_WITH_ASSIGNED_RESOURCES = [
    "assigned",
    "accepted",
    "preparing",
    "starting",
    "running",
]


class ClusterResources(BaseModel):
    total_cpus: int
    total_ram: ByteSize
    node_ids: list[str]


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


# TODO: we need to check only services on the monitored nodes, maybe with some specific labels/names
async def pending_service_tasks_with_insufficient_resources(
    service_labels: list[Label],
) -> list[Task]:
    """
    Tasks pending with insufficient resources are
    - pending
    - have an error message with "insufficient resources"
    - are not scheduled on any node
    """
    # SEE  https://github.com/aio-libs/aiodocker
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


async def compute_cluster_total_resources(node_labels: list[str]) -> ClusterResources:
    """
    We compile RAM and CPU capabilities of each node who have the label sidecar
    Total resources of the cluster
    """
    cluster_resources_counter = collections.Counter({"total_ram": 0, "total_cpus": 0})
    async with aiodocker.Docker() as docker:
        nodes = await docker.nodes.list(
            filters={"node.label": [f"{label}=true" for label in node_labels]}
        )

        node_ids = []
        for node in nodes:
            cluster_resources_counter.update(
                {
                    "total_ram": node["Description"]["Resources"]["MemoryBytes"],
                    "total_cpus": node["Description"]["Resources"]["NanoCPUs"]
                    / _NANO_CPU,
                }
            )
            node_ids.append(node["ID"])

    return ClusterResources.parse_obj(
        dict(cluster_resources_counter) | {"node_ids": node_ids}
    )


async def compute_cluster_used_resources(node_ids: list[str]) -> ClusterResources:
    cluster_resources_counter = collections.Counter({"total_ram": 0, "total_cpus": 0})
    async with aiodocker.Docker() as docker:
        for node_id in node_ids:
            all_tasks_on_node = await docker.tasks.list(filters={"node": node_id})
            for task in all_tasks_on_node:
                if task["Status"]["State"] in _TASK_STATUS_WITH_ASSIGNED_RESOURCES:
                    task_reservations = (
                        task["Spec"].get("Resources", {}).get("Reservations", {})
                    )
                    cluster_resources_counter.update(
                        {
                            "total_ram": task_reservations.get("MemoryBytes", 0),
                            "total_cpus": task_reservations.get("NanoCPUs", 0)
                            / _NANO_CPU,
                        }
                    )
    return ClusterResources.parse_obj(
        dict(cluster_resources_counter) | {"node_ids": node_ids}
    )


# async def compute_cluster_pending_resources(node_ids: list[str]) -> ClusterResources:
#     cluster_resources_counter = collections.Counter({"total_ram": 0, "total_cpus": 0})
#     async with aiodocker.Docker() as docker:
#         for node_id in node_ids:
#             all_tasks_on_node = await docker.tasks.list(filters={"node": node_id})
#             for task in all_tasks_on_node:
#                 if task["Status"]["State"] in ["pending"]:
#                     task_reservations = (
#                         task["Spec"].get("Resources", {}).get("Reservations", {})
#                     )
#                     cluster_resources_counter.update(
#                         {
#                             "total_ram": task_reservations.get("MemoryBytes", 0),
#                             "total_cpus": task_reservations.get("NanoCPUs", 0)
#                             / _NANO_CPU,
#                         }
#                     )
#             for task in tasks:
#                 if (
#                     task["Status"]["State"] == "pending"
#                     and task["Status"]["Message"] == "pending task scheduling"
#                     and "insufficient resources on"
#                     in task["Status"].get("Err", "no error")
#                 ):
#     return ClusterResources.parse_obj(
#         dict(cluster_resources_counter) | {"node_ids": node_ids}
#     )
