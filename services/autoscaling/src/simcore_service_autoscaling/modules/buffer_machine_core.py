from collections import Counter, defaultdict
from typing import Final

from aws_library.ec2.models import AWSTagKey, AWSTagValue, EC2Tags
from fastapi import FastAPI
from pydantic import parse_obj_as

from ..core.settings import get_application_settings
from .auto_scaling_mode_base import BaseAutoscaling
from .ec2 import get_ec2_client
from .ssm import get_ssm_client

_BUFFER_EC2_TAGS: EC2Tags = {
    parse_obj_as(AWSTagKey, "buffer-machine"): parse_obj_as(AWSTagValue, "true")
}

_PREPULL_COMMAND_NAME: Final[str] = "docker images prepulling"

#
# Possible settings to cope with different types
#
# g4dn.xlarge: 2 buffers
# g4dn.8xlarge: 2 buffers
# it would make sense to share some buffer among compatible types instead of keeping a separation
# analyse input settings to create a type of dictionary?
# {g4dn.*: {number:3, prepulling:{s4l-core:3.2.27, jupyter-math:3.4.5}}}


def _get_buffer_ec2_tags(app: FastAPI, auto_scaling_mode: BaseAutoscaling) -> EC2Tags:
    # TODO: add target ec2 type?
    # pre pulling depends on the EC2 type, e.g. it makes no sense to pull s4l on a non-GPU EC2!
    return auto_scaling_mode.get_ec2_tags(app) | _BUFFER_EC2_TAGS


async def monitor_buffer_machines(
    app: FastAPI, *, auto_scaling_mode: BaseAutoscaling
) -> None:
    """Buffer machine creation works like so:
    1. a EC2 is created with an EBS attached volume wO auto prepulling and wO auto connect to swarm
    2. once running, a AWS SSM task is started to pull the necessary images in a controlled way
    3. once the task is completed, the EC2 is stopped and is made available as a buffer EC2
    4. once needed the buffer machine is started, and as it is up a SSM task is sent to connect to the swarm,
    5. the usual then happens
    """
    ec2_client = get_ec2_client(app)
    ssm_client = get_ssm_client(app)
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    ready_buffer_instances = await ec2_client.get_instances(
        key_names=[app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_KEY_NAME],
        tags=_get_buffer_ec2_tags(app, auto_scaling_mode),
        state_names=["stopped"],
    )
    num_of_buffer_instances_by_type = Counter(_.type for _ in ready_buffer_instances)

    buffer_instances_to_terminate_by_type = defaultdict()
    for (
        instance_type,
        instance_type_boot,
    ) in app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES.items():
        if (
            num_of_buffer_instances_by_type[instance_type]
            > instance_type_boot.buffer_count
        ):
            buffer_instances_to_terminate_by_type[instance_type] = (
                num_of_buffer_instances_by_type[instance_type]
                - instance_type_boot.buffer_count
            )
    # find the instance ids
    instance_ids_to_terminate = []
    for instance in ready_buffer_instances:
        if buffer_instances_to_terminate_by_type[instance.type]:
            instance_ids_to_terminate.append(instance.id)
            buffer_instances_to_terminate_by_type[instance.type] -= 1

    # observe current state:
    # list currently available buffer machines

    pending_instances = await ec2_client.get_instances(
        key_names=[app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_KEY_NAME],
        tags=_get_buffer_ec2_tags(app, auto_scaling_mode),
        state_names=["pending"],
    )
    # list buffer machines being created now
    buffer_instances = await ec2_client.get_instances(
        key_names=[app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_KEY_NAME],
        tags=_get_buffer_ec2_tags(app, auto_scaling_mode),
        state_names=["running"],
    )

    # for the running images we should check if image pulling was completed
    instances_to_send_command_to = []
    instances_to_stop = []
    for instance in buffer_instances:
        commands = await ssm_client.list_commands_on_instance(instance.id)
        command_found = False
        for command in commands:
            if command.name == _PREPULL_COMMAND_NAME:
                command_found = True
                if command.status == "Success":
                    # the command is completed, we can stop the instance
                    instances_to_stop.append(instance)
                    break
        if not command_found:
            instances_to_send_command_to.append(instance)

    if instances_to_stop:
        await ec2_client.stop_instances(instances_to_stop)

    for instance in instances_to_send_command_to:
        await ssm_client.send_command(
            instance.id,
            "docker pull",
            _PREPULL_COMMAND_NAME,
        )
