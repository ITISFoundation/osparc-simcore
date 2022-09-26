""" Free helper functions for docker API

"""

import aiodocker
from pydantic import BaseModel, PositiveInt

from .utils import bytesto


async def need_resources() -> bool:
    # SEE  https://github.com/aio-libs/aiodocker

    async with aiodocker.Docker() as docker:
        serv = await docker.services.list()
        # We need the data of each task and the data of each node to know if we need to scale up or not
        # Test if some tasks are in a pending mode because of a lack of resources
        for service in serv:
            tasks = service.tasks()
            for task in tasks:
                if (
                    task["Status"]["State"] == "pending"
                    and task["Status"]["Message"] == "pending task scheduling"
                    and "insufficient resources on" in task["Status"]["Err"]
                ):
                    return True
        return False


class NodesResources(BaseModel):
    total_cpus: int
    total_ram: int
    node_ids: list[str]


async def check_node_resources() -> NodesResources:

    async with aiodocker.Docker() as docker:
        nodes = await docker.nodes.list()
        # We compile RAM and CPU capabilities of each node who have the label sidecar
        # TODO take in account personalized workers
        # Total resources of the cluster
        nodes_sidecar_data = []
        for node in nodes:
            for label in node.get("Spec", {}).get("Labels", {}):
                if label == "sidecar":
                    nodes_sidecar_data.append(
                        {
                            "ID": node.attrs["ID"],
                            "RAM": bytesto(
                                node.attrs["Description"]["Resources"]["MemoryBytes"],
                                "g",
                                bsize=1024,
                            ),
                            "CPU": int(
                                node.attrs["Description"]["Resources"]["NanoCPUs"]
                            )
                            / 1000000000,
                        }
                    )

        total_nodes_cpus = 0
        total_nodes_ram = 0
        nodes_ids = []
        for node in nodes_sidecar_data:
            total_nodes_cpus = total_nodes_cpus + node["CPU"]
            total_nodes_ram = total_nodes_ram + node["RAM"]
            nodes_ids.append(node["ID"])

        return NodesResources.parse_obj(
            {
                "total_cpus": total_nodes_cpus,
                "total_ram": total_nodes_ram,
                "nodes_ids": nodes_ids,
            }
        )


class TasksResources(BaseModel):
    total_cpus_running_tasks: PositiveInt
    total_ram_running_tasks: PositiveInt
    total_cpus_pending_tasks: PositiveInt
    total_ram_pending_tasks: PositiveInt
    count_tasks_pending: PositiveInt


async def check_tasks_resources(nodes_ids) -> TasksResources:
    # TODO discuss with the team consideration between limits and reservations on dy services
    total_tasks_cpus = 0
    total_tasks_ram = 0
    tasks_ressources = []
    total_pending_tasks_cpus = 0
    total_pending_tasks_ram = 0
    tasks_pending_ressources = []

    async with aiodocker.Docker() as docker:
        services = await docker.services.list()
        count_tasks_pending = 0
        for service in services:
            tasks = service.tasks()
            for task in tasks:

                if task["Status"]["State"] == "running" and task["NodeID"] in nodes_ids:
                    if (
                        reservations := task["Spec"]
                        .get("Resources", {})
                        .get("Reservations")
                    ):
                        ram = 0
                        cpu = 0
                        if "MemoryBytes" in reservations:
                            ram = bytesto(
                                reservations["MemoryBytes"],
                                "g",
                                bsize=1024,
                            )
                        if "NanoCPUs" in reservations:
                            cpu = int(reservations["NanoCPUs"]) / 1000000000

                        tasks_ressources.append(
                            {"ID": task["ID"], "RAM": ram, "CPU": cpu}
                        )

                elif (
                    task["Status"]["State"] == "pending"
                    and task["Status"]["Message"] == "pending task scheduling"
                    and "insufficient resources on" in task["Status"]["Err"]
                ):
                    count_tasks_pending = count_tasks_pending + 1

                    if (
                        reservations := task["Spec"]
                        .get("Resources", {})
                        .get("Reservations")
                    ):
                        ram = 0
                        cpu = 0
                        if "MemoryBytes" in reservations:
                            ram = bytesto(
                                reservations["MemoryBytes"],
                                "g",
                                bsize=1024,
                            )
                        if "NanoCPUs" in reservations:
                            cpu = int(reservations["NanoCPUs"]) / 1000000000
                        tasks_pending_ressources.append(
                            {"ID": task["ID"], "RAM": ram, "CPU": cpu}
                        )

        total_tasks_cpus = 0
        total_tasks_ram = 0
        for task in tasks_ressources:
            total_tasks_cpus = total_tasks_cpus + task["CPU"]
            total_tasks_ram = total_tasks_ram + task["RAM"]

        for task in tasks_pending_ressources:
            total_pending_tasks_cpus = total_pending_tasks_cpus + task["CPU"]
            total_pending_tasks_ram = total_pending_tasks_ram + task["RAM"]
        return TasksResources.parse_obj(
            {
                "total_cpus_running_tasks": total_tasks_cpus,
                "total_ram_running_tasks": total_tasks_ram,
                "total_cpus_pending_tasks": total_pending_tasks_cpus,
                "total_ram_pending_tasks": total_pending_tasks_ram,
                "count_tasks_pending": count_tasks_pending,
            }
        )
