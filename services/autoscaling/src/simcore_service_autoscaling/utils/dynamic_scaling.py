import datetime
import logging
import re
from copy import deepcopy
from typing import Final

from fastapi import FastAPI
from models_library.generated_models.docker_rest_api import Node, Task

from ..core.errors import Ec2InvalidDnsNameError
from ..core.settings import ApplicationSettings, get_application_settings
from ..models import AssociatedInstance, EC2InstanceData, EC2InstanceType, Resources
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
    pending_task: Task,
    list_of_instance_to_tasks: list[tuple[EC2InstanceType, list[Task]]],
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


async def try_assigning_task_to_pending_instances(
    app: FastAPI,
    pending_task: Task,
    list_of_pending_instance_to_tasks: list[tuple[EC2InstanceData, list[Task]]],
    type_to_instance_map: dict[str, EC2InstanceType],
) -> bool:
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    instance_max_time_to_start = (
        app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_START_TIME
    )
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
            now = datetime.datetime.now(datetime.timezone.utc)
            time_since_launch = now - instance.launch_time
            estimated_time_to_completion = (
                instance.launch_time + instance_max_time_to_start - now
            )
            await log_tasks_message(
                app,
                [pending_task],
                f"adding machines to the cluster (time waiting: {time_since_launch}, est. remaining time: {estimated_time_to_completion})...please wait...",
            )
            await progress_tasks_message(
                app,
                [pending_task],
                time_since_launch.total_seconds()
                / instance_max_time_to_start.total_seconds(),
            )
            return True
    return False


async def ec2_startup_script(app_settings: ApplicationSettings) -> str:
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    startup_commands = deepcopy(
        app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_CUSTOM_BOOT_SCRIPTS
    )
    startup_commands.append(await utils_docker.get_docker_swarm_join_bash_command())
    if app_settings.AUTOSCALING_REGISTRY:
        if pull_image_cmd := utils_docker.get_docker_pull_images_on_start_bash_command(
            app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_PRE_PULL_IMAGES
        ):
            startup_commands.append(
                " && ".join(
                    [
                        utils_docker.get_docker_login_on_start_bash_command(
                            app_settings.AUTOSCALING_REGISTRY
                        ),
                        pull_image_cmd,
                    ]
                )
            )
            startup_commands.append(
                utils_docker.get_docker_pull_images_crontab(
                    app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_PRE_PULL_IMAGES_CRON_INTERVAL
                ),
            )

    return " && ".join(startup_commands)
