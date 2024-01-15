import functools
import logging
import re
from typing import Final

from aws_library.ec2.models import (
    EC2InstanceBootSpecific,
    EC2InstanceData,
    EC2InstanceType,
)
from models_library.generated_models.docker_rest_api import Node
from types_aiobotocore_ec2.literals import InstanceTypeType

from ..core.errors import Ec2InstanceInvalidError, Ec2InvalidDnsNameError
from ..core.settings import ApplicationSettings
from ..models import (
    AssignedTasksToInstance,
    AssignedTasksToInstanceType,
    AssociatedInstance,
)
from ..modules.auto_scaling_mode_base import BaseAutoscaling
from . import utils_docker

_EC2_INTERNAL_DNS_RE: Final[re.Pattern] = re.compile(r"^(?P<host_name>ip-[^.]+).*$")
_logger = logging.getLogger(__name__)


def node_host_name_from_ec2_private_dns(
    ec2_instance_data: EC2InstanceData,
) -> str:
    """returns the node host name 'ip-10-2-3-22' from the ec2 private dns
    Raises:
        Ec2InvalidDnsNameError: if the dns name does not follow the expected pattern
    """
    if match := re.match(_EC2_INTERNAL_DNS_RE, ec2_instance_data.aws_private_dns):
        host_name: str = match.group("host_name")
        return host_name
    raise Ec2InvalidDnsNameError(aws_private_dns_name=ec2_instance_data.aws_private_dns)


def node_ip_from_ec2_private_dns(
    ec2_instance_data: EC2InstanceData,
) -> str:
    """returns the node ipv4 from the ec2 private dns string
    Raises:
        Ec2InvalidDnsNameError: if the dns name does not follow the expected pattern
    """
    return (
        node_host_name_from_ec2_private_dns(ec2_instance_data)
        .removeprefix("ip-")
        .replace("-", ".")
    )


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
            _logger.exception("Unexpected EC2 private dns name")
            non_associated_instances.append(instance_data)
            continue

        if node := next(iter(filter(_find_node_with_name, nodes)), None):
            associated_instances.append(
                AssociatedInstance(node=node, ec2_instance=instance_data)
            )
        else:
            non_associated_instances.append(instance_data)
    return associated_instances, non_associated_instances


async def ec2_startup_script(
    ec2_boot_specific: EC2InstanceBootSpecific, app_settings: ApplicationSettings
) -> str:
    startup_commands = ec2_boot_specific.custom_boot_scripts.copy()
    startup_commands.append(await utils_docker.get_docker_swarm_join_bash_command())
    if app_settings.AUTOSCALING_REGISTRY:  # noqa: SIM102
        if pull_image_cmd := utils_docker.get_docker_pull_images_on_start_bash_command(
            ec2_boot_specific.pre_pull_images
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
                    ec2_boot_specific.pre_pull_images_cron_interval
                ),
            )

    return " && ".join(startup_commands)


def _instance_type_by_type_name(
    ec2_type: EC2InstanceType, *, type_name: InstanceTypeType | None
) -> bool:
    if type_name is None:
        return True
    return bool(ec2_type.name == type_name)


def _instance_type_map_by_type_name(
    mapping: AssignedTasksToInstanceType, *, type_name: InstanceTypeType | None
) -> bool:
    return _instance_type_by_type_name(mapping.instance_type, type_name=type_name)


def _instance_data_map_by_type_name(
    mapping: AssignedTasksToInstance, *, type_name: InstanceTypeType | None
) -> bool:
    if type_name is None:
        return True
    return bool(mapping.instance.type == type_name)


def filter_by_task_defined_instance(
    instance_type_name: InstanceTypeType | None,
    active_instances_to_tasks: list[AssignedTasksToInstance],
    pending_instances_to_tasks: list[AssignedTasksToInstance],
    drained_instances_to_tasks: list[AssignedTasksToInstance],
    needed_new_instance_types_for_tasks: list[AssignedTasksToInstanceType],
) -> tuple[
    list[AssignedTasksToInstance],
    list[AssignedTasksToInstance],
    list[AssignedTasksToInstance],
    list[AssignedTasksToInstanceType],
]:
    return (
        list(
            filter(
                functools.partial(
                    _instance_data_map_by_type_name, type_name=instance_type_name
                ),
                active_instances_to_tasks,
            )
        ),
        list(
            filter(
                functools.partial(
                    _instance_data_map_by_type_name, type_name=instance_type_name
                ),
                pending_instances_to_tasks,
            )
        ),
        list(
            filter(
                functools.partial(
                    _instance_data_map_by_type_name, type_name=instance_type_name
                ),
                drained_instances_to_tasks,
            )
        ),
        list(
            filter(
                functools.partial(
                    _instance_type_map_by_type_name, type_name=instance_type_name
                ),
                needed_new_instance_types_for_tasks,
            )
        ),
    )


def find_selected_instance_type_for_task(
    instance_type_name: InstanceTypeType,
    available_ec2_types: list[EC2InstanceType],
    auto_scaling_mode: BaseAutoscaling,
    task,
) -> EC2InstanceType:
    filtered_instances = list(
        filter(
            functools.partial(
                _instance_type_by_type_name, type_name=instance_type_name
            ),
            available_ec2_types,
        )
    )
    if not filtered_instances:
        msg = (
            f"Task {task} requires an unauthorized EC2 instance type."
            f"Asked for {instance_type_name}, authorized are {available_ec2_types}. Please check!"
        )
        raise Ec2InstanceInvalidError(msg=msg)

    assert len(filtered_instances) == 1  # nosec
    selected_instance = filtered_instances[0]

    # check that the assigned resources and the machine resource fit
    if (
        auto_scaling_mode.get_task_required_resources(task)
        > selected_instance.resources
    ):
        msg = (
            f"Task {task} requires more resources than the selected instance provides."
            f" Asked for {selected_instance}, but task needs {auto_scaling_mode.get_task_required_resources(task)}. Please check!"
        )
        raise Ec2InstanceInvalidError(msg=msg)

    return selected_instance
