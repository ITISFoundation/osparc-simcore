""" Free helper functions for docker API

"""

import collections
from typing import Final

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


# TODO: we need to check only services on the monitored nodes, maybe with some specific labels/names
async def pending_services_with_insufficient_resources() -> bool:
    """
    We need the data of each task and the data of each node to know if we need to scale up or not
    Test if some tasks are in a pending mode because of a lack of resources
    """
    # SEE  https://github.com/aio-libs/aiodocker

    async with aiodocker.Docker() as docker:
        services = await docker.services.list()
        for service in services:
            tasks = await docker.tasks.list(
                filters={"service": service["Spec"]["Name"]}
            )
            for task in tasks:
                if (
                    task["Status"]["State"] == "pending"
                    and task["Status"]["Message"] == "pending task scheduling"
                    and "insufficient resources on"
                    in task["Status"].get("Err", "no error")
                ):
                    return True
        return False


async def compute_cluster_total_resources(node_labels: list[str]) -> ClusterResources:
    """
    We compile RAM and CPU capabilities of each node who have the label sidecar
    Total resources of the cluster
    """

    async with aiodocker.Docker() as docker:
        nodes = await docker.nodes.list(
            filters={"node.label": [f"{label}=true" for label in node_labels]}
        )

        cluster_resources_counter = collections.Counter(
            {"total_ram": 0, "total_cpus": 0}
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
