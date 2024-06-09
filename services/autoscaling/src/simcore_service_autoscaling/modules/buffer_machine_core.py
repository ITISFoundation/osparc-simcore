from collections import defaultdict
from dataclasses import dataclass, field
from typing import Final, cast

from aws_library.ec2.client import SimcoreEC2API
from aws_library.ec2.models import (
    AWSTagKey,
    AWSTagValue,
    EC2InstanceConfig,
    EC2InstanceData,
    EC2Tags,
)
from fastapi import FastAPI
from pydantic import NonNegativeInt, parse_obj_as

#
# Possible settings to cope with different types
#
# g4dn.xlarge: 2 buffers
# g4dn.8xlarge: 2 buffers
# it would make sense to share some buffer among compatible types instead of keeping a separation
# analyse input settings to create a type of dictionary?
# {g4dn.*: {number:3, prepulling:{s4l-core:3.2.27, jupyter-math:3.4.5}}}
from types_aiobotocore_ec2.literals import InstanceTypeType

from ..core.settings import ApplicationSettings, get_application_settings
from .auto_scaling_mode_base import BaseAutoscaling
from .ec2 import get_ec2_client
from .ssm import get_ssm_client

_BUFFER_EC2_TAGS: EC2Tags = {
    parse_obj_as(AWSTagKey, "buffer-machine"): parse_obj_as(AWSTagValue, "true")
}

_PREPULL_COMMAND_NAME: Final[str] = "docker images prepulling"


@dataclass(kw_only=True, slots=True)
class WarmBufferPool:
    ready_instances: set[EC2InstanceData] = field(default_factory=set)
    pending_instances: set[EC2InstanceData] = field(default_factory=set)
    waiting_to_pull_instances: set[EC2InstanceData] = field(default_factory=set)
    pulling_instances: set[EC2InstanceData] = field(default_factory=set)
    stopping_instances: set[EC2InstanceData] = field(default_factory=set)

    def all_instances(self) -> set[EC2InstanceData]:
        """sorted by importance"""
        return self.ready_instances.union(
            self.stopping_instances,
            self.pulling_instances,
            self.waiting_to_pull_instances,
            self.pending_instances,
        )

    def remove_instance(self, instance: EC2InstanceData) -> None:
        for _ in (
            self.pending_instances,
            self.waiting_to_pull_instances,
            self.pulling_instances,
            self.stopping_instances,
            self.ready_instances,
        ):
            try:
                _.remove(instance)
            except KeyError:
                continue
            else:
                return


def _get_buffer_ec2_tags(app: FastAPI, auto_scaling_mode: BaseAutoscaling) -> EC2Tags:
    return auto_scaling_mode.get_ec2_tags(app) | _BUFFER_EC2_TAGS


async def _create_buffer_machine(
    ec2_client: SimcoreEC2API,
    app_settings: ApplicationSettings,
    *,
    instance_config: EC2InstanceConfig,
    machines_count: NonNegativeInt,
) -> list[EC2InstanceData]:
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    return await ec2_client.start_aws_instance(
        instance_config,
        min_number_of_instances=machines_count,
        number_of_instances=machines_count,
        max_total_number_of_instances=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES,
    )


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

    # 1. Analyze the current state by type
    all_buffer_instances = await ec2_client.get_instances(
        key_names=[app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_KEY_NAME],
        tags=_get_buffer_ec2_tags(app, auto_scaling_mode),
        state_names=["stopped", "pending", "running", "stopping"],
    )

    current_warm_buffer_pools: dict[InstanceTypeType, WarmBufferPool] = defaultdict(
        WarmBufferPool
    )
    for instance in all_buffer_instances:
        match instance.state:
            case "stopped":
                current_warm_buffer_pools[instance.type].ready_instances.add(instance)
            case "pending":
                current_warm_buffer_pools[instance.type].pending_instances.add(instance)
            case "stopping":
                current_warm_buffer_pools[instance.type].stopping_instances.add(
                    instance
                )
            case "running":
                if "pulling" in instance.tags:
                    current_warm_buffer_pools[instance.type].pulling_instances.add(
                        instance
                    )
                else:
                    current_warm_buffer_pools[
                        instance.type
                    ].waiting_to_pull_instances.add(instance)
            case _:
                pass

    # 2. Terminate the instances that we do not need by removing first pending,
    # then running/pulling, then stopping and after that ready once
    # and remove all the onces that are not supposed to be there (if EC2_INSTANCES_ALLOWED_TYPES changed)
    allowed_instance_types = set(
        app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES
    )
    if instance_types_to_completely_eliminate := set(
        current_warm_buffer_pools
    ).difference(allowed_instance_types):
        instances_to_terminate = set()
        for ec2_type in instance_types_to_completely_eliminate:
            instances_to_terminate.union(
                current_warm_buffer_pools[ec2_type].all_instances()
            )
        await ec2_client.terminate_instances(instances_to_terminate)
        for ec2_type in instance_types_to_completely_eliminate:
            current_warm_buffer_pools.pop(ec2_type)

    instances_to_terminate: set[EC2InstanceData] = set()
    for (
        ec2_type,
        ec2_boot_config,
    ) in app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES.items():
        terminateable_instances = set(
            list(
                current_warm_buffer_pools[
                    cast(InstanceTypeType, ec2_type)
                ].all_instances()
            )[ec2_boot_config.buffer_count :]
        )
        instances_to_terminate.union(terminateable_instances)
    if instances_to_terminate:
        await ec2_client.terminate_instances(instances_to_terminate)
        for instance in instances_to_terminate:
            current_warm_buffer_pools[instance.type].remove_instance(instance)

    # for the running images we should check if image pulling was completed
    # instances_to_send_command_to = []
    # instances_to_stop = []
    # for instance in buffer_instances:
    #     commands = await ssm_client.list_commands_on_instance(instance.id)
    #     command_found = False
    #     for command in commands:
    #         if command.name == _PREPULL_COMMAND_NAME:
    #             command_found = True
    #             if command.status == "Success":
    #                 # the command is completed, we can stop the instance
    #                 instances_to_stop.append(instance)
    #                 break
    #     if not command_found:
    #         instances_to_send_command_to.append(instance)

    # if instances_to_stop:
    #     await ec2_client.stop_instances(instances_to_stop)

    # for instance in instances_to_send_command_to:
    #     await ssm_client.send_command(
    #         instance.id,
    #         "docker pull",
    #         _PREPULL_COMMAND_NAME,
    #     )
