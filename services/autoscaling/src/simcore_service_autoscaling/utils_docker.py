""" Free helper functions for docker API

"""

import collections
from typing import Any, Final, TypedDict

import aiodocker
from pydantic import BaseModel, ByteSize, NonNegativeInt

from .utils import bytesto


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


class ClusterResources(BaseModel):
    total_cpus: int
    total_ram: ByteSize
    node_ids: list[str]


_NANO_CPU: Final[float] = 10**9


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


class TasksResources(BaseModel):
    total_cpus_running_tasks: NonNegativeInt
    total_ram_running_tasks: NonNegativeInt
    total_cpus_pending_tasks: NonNegativeInt
    total_ram_pending_tasks: NonNegativeInt
    count_tasks_pending: NonNegativeInt


class ReservedResources(TypedDict):
    RAM: float
    CPU: int
    # NOTE: future add VRAM, AIRAM
    # SEE https://github.com/ITISFoundation/osparc-simcore/pull/3364#discussion_r987821694


def _get_reserved_resources(reservations: dict[str, Any]) -> ReservedResources:
    ram: float = 0.0
    cpu: int = 0
    if "MemoryBytes" in reservations:
        ram = bytesto(
            reservations["MemoryBytes"],
            "g",
            bsize=1024,
        )
    if "NanoCPUs" in reservations:
        cpu = int(reservations["NanoCPUs"]) / 1_000_000_000
    return {"RAM": ram, "CPU": cpu}


async def compute_cluster_used_resources(nodes_ids: list[str]) -> TasksResources:
    total_tasks_cpus = 0
    total_tasks_ram = 0
    tasks_resources = []
    total_pending_tasks_cpus = 0
    total_pending_tasks_ram = 0
    tasks_pending_resources = []

    async with aiodocker.Docker() as docker:

        services = await docker.services.list()
        for service in services:
            tasks = await docker.tasks.list(
                filters={"service": service["Spec"]["Name"]}
            )
            for task in tasks:
                if (
                    task["Status"]["State"] == "running"
                    and task["NodeID"] in nodes_ids
                    and (
                        reservations := task["Spec"]
                        .get("Resources", {})
                        .get("Reservations")
                    )
                ):
                    tasks_resources.append(
                        {"ID": task["ID"], **_get_reserved_resources(reservations)}
                    )

                elif (
                    task["Status"]["State"] == "pending"
                    and task["Status"]["Message"] == "pending task scheduling"
                    and "insufficient resources on" in task["Status"]["Err"]
                    and (
                        reservations := task["Spec"]
                        .get("Resources", {})
                        .get("Reservations")
                    )
                ):
                    tasks_pending_resources.append(
                        {"ID": task["ID"], **_get_reserved_resources(reservations)}
                    )

        total_tasks_cpus = 0
        total_tasks_ram = 0
        for task in tasks_resources:
            total_tasks_cpus += task["CPU"]
            total_tasks_ram += task["RAM"]

        for task in tasks_pending_resources:
            total_pending_tasks_cpus += task["CPU"]
            total_pending_tasks_ram += task["RAM"]

        return TasksResources(
            total_cpus_running_tasks=total_tasks_cpus,
            total_ram_running_tasks=total_tasks_ram,
            total_cpus_pending_tasks=total_pending_tasks_cpus,
            total_ram_pending_tasks=total_pending_tasks_ram,
            count_tasks_pending=len(tasks_pending_resources),
        )
