import datetime
import logging
import re
from typing import Final

from fastapi import FastAPI
from models_library.generated_models.docker_rest_api import Node, Task

from ..core.errors import Ec2InvalidDnsNameError
from ..models import AssociatedInstance, EC2Instance, EC2InstanceData, Resources
from . import utils_docker
from .rabbitmq import log_tasks_message, progress_tasks_message

logger = logging.getLogger(__name__)


_EC2_INTERNAL_DNS_RE: Final[re.Pattern] = re.compile(r"^(?P<ip>ip-[0-9-]+).+$")


def node_host_name_from_ec2_private_dns(
    ec2_instance_data: EC2InstanceData,
) -> str:
    if match := re.match(_EC2_INTERNAL_DNS_RE, ec2_instance_data.aws_private_dns):
        return match.group(1)
    raise Ec2InvalidDnsNameError(aws_private_dns_name=ec2_instance_data.aws_private_dns)


async def associate_ec2_instances_with_nodes(
    nodes: list[Node], ec2_instances: list[EC2InstanceData]
) -> tuple[list[AssociatedInstance], list[EC2InstanceData]]:
    """returns the associated and non-associated instances"""
    associated_instances: list[AssociatedInstance] = []
    non_associated_instances: list[EC2InstanceData] = []

    def _find_node_with_name(node: Node) -> bool:
        assert node.Description  # nosec
        return bool(node.Description.Hostname == docker_node_name)

    for instance_data in ec2_instances:
        try:
            docker_node_name = node_host_name_from_ec2_private_dns(instance_data)
        except Ec2InvalidDnsNameError:
            logger.exception("Unexcepted EC2 private dns name")
            non_associated_instances.append(instance_data)
            continue

        if node := next(iter(filter(_find_node_with_name, nodes)), None):
            associated_instances.append(AssociatedInstance(node, instance_data))
        else:
            non_associated_instances.append(instance_data)
    return associated_instances, non_associated_instances


def try_assigning_task_to_node(
    pending_task: Task, instance_to_tasks: list[tuple[AssociatedInstance, list[Task]]]
) -> bool:
    for instance, node_assigned_tasks in instance_to_tasks:
        instance_total_resource = utils_docker.get_node_total_resources(instance.node)
        tasks_needed_resources = utils_docker.compute_tasks_needed_resources(
            node_assigned_tasks
        )
        if (
            instance_total_resource - tasks_needed_resources
        ) >= utils_docker.get_max_resources_from_docker_task(pending_task):
            node_assigned_tasks.append(pending_task)
            return True
    return False


def try_assigning_task_to_instances(
    pending_task: Task, list_of_instance_to_tasks: list[tuple[EC2Instance, list[Task]]]
) -> bool:
    for instance, instance_assigned_tasks in list_of_instance_to_tasks:
        instance_total_resource = Resources(cpus=instance.cpus, ram=instance.ram)
        tasks_needed_resources = utils_docker.compute_tasks_needed_resources(
            instance_assigned_tasks
        )
        if (
            instance_total_resource - tasks_needed_resources
        ) >= utils_docker.get_max_resources_from_docker_task(pending_task):
            instance_assigned_tasks.append(pending_task)
            return True
    return False


_MINUTE: Final[int] = 60
_AVG_TIME_TO_START_EC2_INSTANCE: Final[int] = 3 * _MINUTE


async def try_assigning_task_to_pending_instances(
    app: FastAPI,
    pending_task: Task,
    list_of_pending_instance_to_tasks: list[tuple[EC2InstanceData, list[Task]]],
    type_to_instance_map: dict[str, EC2Instance],
) -> bool:
    for instance, instance_assigned_tasks in list_of_pending_instance_to_tasks:
        instance_type = type_to_instance_map[instance.type]
        instance_total_resources = Resources(
            cpus=instance_type.cpus, ram=instance_type.ram
        )
        tasks_needed_resources = utils_docker.compute_tasks_needed_resources(
            instance_assigned_tasks
        )
        if (
            instance_total_resources - tasks_needed_resources
        ) >= utils_docker.get_max_resources_from_docker_task(pending_task):
            instance_assigned_tasks.append(pending_task)
            await log_tasks_message(
                app,
                [pending_task],
                "scaling up of cluster in progress...awaiting new machines...please wait...",
            )
            await progress_tasks_message(
                app,
                [pending_task],
                (
                    datetime.datetime.now(datetime.timezone.utc) - instance.launch_time
                ).total_seconds()
                / _AVG_TIME_TO_START_EC2_INSTANCE,
            )
            return True
    return False
