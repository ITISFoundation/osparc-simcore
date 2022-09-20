import logging
import math
from datetime import datetime, timedelta

from .core.settings import AwsSettings
from .utils_aws import AWS_EC2, compose_user_data, start_instance_aws
from .utils_docker import check_node_resources, check_tasks_resources, need_resources

logger = logging.getLogger(__name__)


async def check_dynamic(settings: AwsSettings):
    """
    Check if the swarm need to scale up

    TODO: currently the script has to be executed directly on the manager. Implenting a version that connect with ssh and handle the case when one manager is down to be able to have redundancy
    """
    user_data = compose_user_data(settings.AUTOSCALING_AWS)

    # We need the data of each task and the data of each node to know if we need to scale up or not
    # Test if some tasks are in a pending mode because of a lack of resources
    resources_are_scarce = await need_resources()

    # We compile RAM and CPU capabilities of each node who have the label sidecar
    # TODO take in account personalized workers
    # Total resources of the cluster
    if resources_are_scarce:
        total_nodes = await check_node_resources()
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
        for instance in AWS_EC2:
            # if instance["CPUs"] >= needed_cpus and instance["RAM"] >= needed_ram:
            if instance["CPUs"] >= math.ceil(
                total_tasks.total_cpus_pending_tasks
            ) and instance["RAM"] >= math.ceil(total_tasks.total_ram_pending_tasks):
                now = datetime.now() + timedelta(hours=2)
                dt_string = now.strftime("%d/%m/%Y %H:%M:%S")

                logger.info(
                    "A new EC2 instance has been selected to add more resources to the cluster."
                    " Name : %s"
                    " Cpus : %s"
                    " RAM : %s GB",
                    instance["name"],
                    instance["CPUs"],
                    instance["RAM"],
                )
                start_instance_aws(
                    "ami-097895f2d7d86f07e",
                    instance["name"],
                    "Autoscaling node " + dt_string,
                    "dynamic",
                    user_data,
                )
                break
    else:
        logger.info("No pending task(s) on the swarm detected.")

        # TODO Better algorythm
