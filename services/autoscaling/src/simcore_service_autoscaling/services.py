import logging
import math
from datetime import datetime

from .core.settings import AwsSettings
from .utils_aws import AWS_EC2, start_instance_aws
from .utils_docker import (
    check_tasks_resources,
    get_labelized_nodes_resources,
    pending_services_with_insufficient_resources,
)

logger = logging.getLogger(__name__)


async def check_dynamic(settings: AwsSettings, ami_id: str):
    """
    Check if the swarm need to scale up

    """
    #
    # WARNING: this was just copied here as sample. Needs to be tested and probably rewritten
    # SEE notes in https://github.com/ITISFoundation/osparc-simcore/pull/3364
    #

    # We need the data of each task and the data of each node to know if we need to scale up or not
    # Test if some tasks are in a pending mode because of a lack of resources
    resources_are_scarce = await pending_services_with_insufficient_resources()

    # We compile RAM and CPU capabilities of each node who have the label sidecar
    # Total resources of the cluster
    if resources_are_scarce:
        total_nodes = await get_labelized_nodes_resources()
        total_tasks = await check_tasks_resources(total_nodes.nodes_ids)
        available_cpus = total_nodes.total_cpus - total_tasks.total_cpus_running_tasks
        available_ram = total_nodes.total_ram - total_tasks.total_ram_running_tasks

        logger.info("avail cpuz %s avail ram %s", available_cpus, available_ram)

        needed_cpus = (
            available_cpus - total_tasks.total_cpus_pending_tasks
        ) * -1 + 2  # Cpus used for other tasks
        needed_ram = (
            available_ram - total_tasks.total_ram_pending_tasks
        ) * -1 + 4  # Ram used for other stasks

        logger.info(
            "taskcpus_needed : %s staskRAMneeded : %s",
            total_tasks.total_cpus_pending_tasks,
            total_tasks.total_ram_pending_tasks,
        )
        logger.info(
            "The Swarm currently has %d task(s) in pending mode",
            total_tasks.count_tasks_pending,
        )
        logger.info(
            "Theses task require a total of %s cpus and %s  GB of RAM in order to be executed.",
            needed_cpus,
            needed_ram,
        )
        logger.info(
            "Theses task(s) require a total of %s cps and %s  GB of RAM in order to be executed.",
            math.ceil(total_tasks.total_cpus_pending_tasks),
            math.ceil(total_tasks.total_ram_pending_tasks),
        )

        selected_instance = None
        for instance in AWS_EC2:
            if instance["CPUs"] >= math.ceil(
                total_tasks.total_cpus_pending_tasks
            ) and instance["RAM"] >= math.ceil(total_tasks.total_ram_pending_tasks):
                logger.info(
                    "A new EC2 instance has been selected to add more resources to the cluster."
                    " Name : %s"
                    " Cpus : %s"
                    " RAM : %s GB",
                    instance["name"],
                    instance["CPUs"],
                    instance["RAM"],
                )
                selected_instance = instance

        if selected_instance:
            start_instance_aws(
                settings,
                ami_id,
                instance_type=selected_instance["name"],
                tag=f"Autoscaling node {datetime.utcnow().isoformat()}",
                service_type="dynamic",
            )
        else:
            logger.warning(
                "No instance available for requested resources %s", total_tasks
            )

    else:
        logger.info("No pending task(s) on the swarm detected")
