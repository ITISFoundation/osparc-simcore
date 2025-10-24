import functools
import logging
import typing
from typing import TypeAlias

from aws_library.ec2 import (
    EC2InstanceBootSpecific,
    EC2InstanceData,
    EC2InstanceType,
    Resources,
)
from models_library.generated_models.docker_rest_api import Node
from types_aiobotocore_ec2.literals import InstanceTypeType

from ..core.errors import (
    Ec2InvalidDnsNameError,
    TaskRequirementsAboveRequiredEC2InstanceTypeError,
    TaskRequiresUnauthorizedEC2InstanceTypeError,
)
from ..core.settings import ApplicationSettings
from ..models import AssociatedInstance
from . import utils_docker, utils_ec2

_logger = logging.getLogger(__name__)


def associate_ec2_instances_with_nodes(
    nodes: list[Node], ec2_instances: list[EC2InstanceData]
) -> tuple[list[AssociatedInstance], list[EC2InstanceData]]:
    """returns the associated and non-associated instances"""
    associated_instances: list[AssociatedInstance] = []
    non_associated_instances: list[EC2InstanceData] = []

    def _find_node_with_name(node: Node) -> bool:
        assert node.description  # nosec
        return bool(node.description.hostname == docker_node_name)

    for instance_data in ec2_instances:
        try:
            docker_node_name = utils_ec2.node_host_name_from_ec2_private_dns(
                instance_data
            )
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
    startup_commands.append(
        await utils_docker.get_docker_swarm_join_bash_command(
            join_as_drained=app_settings.AUTOSCALING_DOCKER_JOIN_DRAINED
        )
    )
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    if app_settings.AUTOSCALING_REGISTRY:
        startup_commands.append(
            utils_docker.get_docker_login_on_start_bash_command(
                app_settings.AUTOSCALING_REGISTRY
            )
        )

        if pull_image_cmd := utils_docker.get_docker_pull_images_on_start_bash_command(
            app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_COLD_START_DOCKER_IMAGES_PRE_PULLING
        ):
            startup_commands.append(pull_image_cmd)

    return " && ".join(startup_commands)


@typing.no_type_check  # NOTE: This disable checking by mypy as it cannot handle checking this in reasonable time (>5 minutes) since 1.18.0 (due to large Literal Union it seems)
def _instance_type_by_type_name(
    ec2_type: EC2InstanceType, *, type_name: InstanceTypeType | None
) -> bool:
    return type_name is None or ec2_type.name == type_name


def find_selected_instance_type_for_task(
    instance_type_name: InstanceTypeType,
    available_ec2_types: list[EC2InstanceType],
    task,
    task_required_resources: Resources,
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
        raise TaskRequiresUnauthorizedEC2InstanceTypeError(
            task=task, instance_type=instance_type_name
        )

    assert len(filtered_instances) == 1  # nosec
    selected_instance = filtered_instances[0]

    # check that the assigned resources and the machine resource fit
    if task_required_resources > selected_instance.resources:
        raise TaskRequirementsAboveRequiredEC2InstanceTypeError(
            task=task,
            instance_type=selected_instance,
            resources=task_required_resources,
            resources_diff=task_required_resources - selected_instance.resources,
        )

    return selected_instance


def get_hot_buffer_type(
    available_ec2_types: list[EC2InstanceType],
) -> EC2InstanceType:
    assert len(available_ec2_types) > 0  # nosec
    return available_ec2_types[0]


DrainedNodes: TypeAlias = list[AssociatedInstance]
HotBufferDrainedNodes: TypeAlias = list[AssociatedInstance]
TerminatingNodes: TypeAlias = list[AssociatedInstance]


def sort_drained_nodes(
    app_settings: ApplicationSettings,
    all_drained_nodes: list[AssociatedInstance],
    available_ec2_types: list[EC2InstanceType],
) -> tuple[DrainedNodes, HotBufferDrainedNodes, TerminatingNodes]:
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    # first sort out the drained nodes that started termination
    terminating_nodes = [
        n
        for n in all_drained_nodes
        if utils_docker.get_node_termination_started_since(n.node) is not None
    ]
    remaining_drained_nodes = [
        n for n in all_drained_nodes if n not in terminating_nodes
    ]
    # we need to keep in reserve only the drained nodes of the right type
    hot_buffer_type = get_hot_buffer_type(available_ec2_types)
    # NOTE: we keep only in buffer the drained nodes with the right EC2 type, AND the right amount
    hot_buffer_drained_nodes = [
        node
        for node in remaining_drained_nodes
        if node.ec2_instance.type == hot_buffer_type.name
    ][: app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER]
    # all the others are "normal" drained nodes and may be terminated at some point
    other_drained_nodes = [
        node for node in remaining_drained_nodes if node not in hot_buffer_drained_nodes
    ]
    return (other_drained_nodes, hot_buffer_drained_nodes, terminating_nodes)
