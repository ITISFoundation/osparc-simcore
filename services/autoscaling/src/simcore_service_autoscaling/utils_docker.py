""" Free helper functions for docker API

"""

from typing import Any, TypedDict

import aiodocker
from pydantic import BaseModel, PositiveInt

from .utils import bytesto


async def pending_services_with_insufficient_resources() -> bool:
    """
    We need the data of each task and the data of each node to know if we need to scale up or not
    Test if some tasks are in a pending mode because of a lack of resources
    """
    # SEE  https://github.com/aio-libs/aiodocker

    async with aiodocker.Docker() as docker:
        services = await docker.services.list()
        for service in services:
            tasks = service.tasks()
            for task in tasks:
                if (
                    task["Status"]["State"] == "pending"
                    and task["Status"]["Message"] == "pending task scheduling"
                    and "insufficient resources on" in task["Status"]["Err"]
                ):
                    return True
        return False


class ClusterResources(BaseModel):
    total_cpus: int
    total_ram: int
    nodes_ids: list[str]


async def eval_cluster_resources() -> ClusterResources:
    """
    We compile RAM and CPU capabilities of each node who have the label sidecar
    Total resources of the cluster
    """

    async with aiodocker.Docker() as docker:
        nodes = await docker.nodes.list(filters={"label": "sidecar"})
        nodes_sidecar_data = []
        for node in nodes:
            nodes_sidecar_data.append(
                {
                    "ID": node["ID"],
                    "RAM": bytesto(
                        node["Description"]["Resources"]["MemoryBytes"],
                        "g",
                        bsize=1024,
                    ),
                    "CPU": int(node["Description"]["Resources"]["NanoCPUs"])
                    / 1000000000,
                }
            )

        total_nodes_cpus = 0
        total_nodes_ram = 0
        nodes_ids = []
        for node in nodes_sidecar_data:
            total_nodes_cpus += node["CPU"]
            total_nodes_ram += node["RAM"]
            nodes_ids.append(node["ID"])

        return ClusterResources(
            total_cpus=total_nodes_cpus,
            total_ram=total_nodes_ram,
            nodes_ids=nodes_ids,
        )


class TasksResources(BaseModel):
    total_cpus_running_tasks: PositiveInt
    total_ram_running_tasks: PositiveInt
    total_cpus_pending_tasks: PositiveInt
    total_ram_pending_tasks: PositiveInt
    count_tasks_pending: PositiveInt


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


async def check_tasks_resources(nodes_ids: list[str]) -> TasksResources:
    total_tasks_cpus = 0
    total_tasks_ram = 0
    tasks_resources = []
    total_pending_tasks_cpus = 0
    total_pending_tasks_ram = 0
    tasks_pending_resources = []

    async with aiodocker.Docker() as docker:

        services = await docker.services.list()
        for service in services:
            tasks = service.tasks()
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
