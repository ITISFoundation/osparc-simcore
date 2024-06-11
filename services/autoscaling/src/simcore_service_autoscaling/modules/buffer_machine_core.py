import logging
from collections import defaultdict
from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Any, Final, cast

from aws_library.ec2.models import (
    AWSTagKey,
    AWSTagValue,
    EC2InstanceConfig,
    EC2InstanceData,
    EC2InstanceType,
    EC2Tags,
    Resources,
)
from fastapi import FastAPI
from pydantic import NonNegativeInt, parse_obj_as
from servicelib.logging_utils import log_context
from types_aiobotocore_ec2.literals import InstanceTypeType

from ..core.settings import get_application_settings
from ..utils.auto_scaling_core import ec2_buffer_startup_script
from .auto_scaling_mode_base import BaseAutoscaling
from .ec2 import get_ec2_client
from .ssm import get_ssm_client

_BUFFER_MACHINE_TAG_KEY: Final[AWSTagKey] = parse_obj_as(AWSTagKey, "buffer-machine")
_BUFFER_MACHINE_EC2_TAGS: EC2Tags = {
    _BUFFER_MACHINE_TAG_KEY: parse_obj_as(AWSTagValue, "true")
}
_BUFFER_MACHINE_PULLING_EC2_TAG_KEY: Final[AWSTagKey] = parse_obj_as(
    AWSTagKey, "pulling"
)
_BUFFER_MACHINE_PULLING_COMMAND_ID_EC2_TAG_KEY: Final[AWSTagKey] = parse_obj_as(
    AWSTagKey, "ssm-command-id"
)
_PREPULL_COMMAND_NAME: Final[str] = "docker images pulling"

_logger = logging.getLogger(__name__)


@dataclass(kw_only=True, slots=True)
class WarmBufferPool:
    ready_instances: set[EC2InstanceData] = field(default_factory=set)
    pending_instances: set[EC2InstanceData] = field(default_factory=set)
    waiting_to_pull_instances: set[EC2InstanceData] = field(default_factory=set)
    pulling_instances: set[EC2InstanceData] = field(default_factory=set)
    stopping_instances: set[EC2InstanceData] = field(default_factory=set)

    def __repr__(self) -> str:
        return (
            f"WarmBufferPool(ready-count={len(self.ready_instances)}, "
            f"pending-count={len(self.pending_instances)}, "
            f"waiting-to-pull-count={len(self.waiting_to_pull_instances)}, "
            f"pulling-count={len(self.pulling_instances)}, "
            f"stopping-count={len(self.stopping_instances)})"
        )

    def _sort_by_readyness(
        self, *, invert: bool = False
    ) -> Generator[set[EC2InstanceData], Any, None]:
        order = (
            self.ready_instances,
            self.stopping_instances,
            self.pulling_instances,
            self.waiting_to_pull_instances,
            self.pending_instances,
        )
        if invert:
            yield from reversed(order)
        else:
            yield from order

    def all_instances(self) -> set[EC2InstanceData]:
        """sorted by importance: READY (stopped) > STOPPING >"""
        gen = self._sort_by_readyness()
        return next(gen).union(*(_ for _ in gen))

    def remove_instance(self, instance: EC2InstanceData) -> None:
        for instances in self._sort_by_readyness(invert=True):
            if instance in instances:
                instances.remove(instance)
                break


def _get_buffer_ec2_tags(app: FastAPI, auto_scaling_mode: BaseAutoscaling) -> EC2Tags:
    return auto_scaling_mode.get_ec2_tags(app) | _BUFFER_MACHINE_EC2_TAGS


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
                if _BUFFER_MACHINE_PULLING_EC2_TAG_KEY in instance.tags:
                    current_warm_buffer_pools[instance.type].pulling_instances.add(
                        instance
                    )
                else:
                    current_warm_buffer_pools[
                        instance.type
                    ].waiting_to_pull_instances.add(instance)
            case _:
                pass
    _logger.info("Current warm pools: %s", f"{current_warm_buffer_pools!r}")

    # 2. Terminate unneded warm pools (e.g. if the user changed the allowed instance types)
    allowed_instance_types = set(
        app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES
    )
    if terminateable_warm_pool_types := set(current_warm_buffer_pools).difference(
        allowed_instance_types
    ):
        with log_context(
            _logger,
            logging.INFO,
            msg=f"removing warm buffer pools: {terminateable_warm_pool_types}",
        ):
            instances_to_terminate: set[EC2InstanceData] = set()
            for ec2_type in terminateable_warm_pool_types:
                instances_to_terminate.union(
                    current_warm_buffer_pools[ec2_type].all_instances()
                )
            await ec2_client.terminate_instances(instances_to_terminate)
            for ec2_type in terminateable_warm_pool_types:
                current_warm_buffer_pools.pop(ec2_type)

    # 3 add/remove buffer instances if needed based on needed buffer counts
    missing_instances: dict[InstanceTypeType, NonNegativeInt] = defaultdict(int)
    unneeded_instances: set[EC2InstanceData] = set()
    for (
        ec2_type,
        ec2_boot_config,
    ) in app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES.items():
        instance_type = cast(InstanceTypeType, ec2_type)
        all_pool_instances = current_warm_buffer_pools[instance_type].all_instances()
        if len(all_pool_instances) < ec2_boot_config.buffer_count:
            missing_instances[instance_type] += ec2_boot_config.buffer_count - len(
                all_pool_instances
            )
        else:
            terminateable_instances = set(
                list(all_pool_instances)[ec2_boot_config.buffer_count :]
            )
            unneeded_instances.union(terminateable_instances)
    for ec2_type, num_to_start in missing_instances.items():
        ec2_boot_specific = (
            app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES[ec2_type]
        )
        await ec2_client.start_aws_instance(
            EC2InstanceConfig(
                type=EC2InstanceType(
                    name=ec2_type,
                    resources=Resources.create_as_empty(),  # fake resources
                ),
                tags=_get_buffer_ec2_tags(app, auto_scaling_mode),
                startup_script=ec2_buffer_startup_script(
                    ec2_boot_specific, app_settings
                ),
                ami_id=ec2_boot_specific.ami_id,
                key_name=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_KEY_NAME,
                security_group_ids=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_SECURITY_GROUP_IDS,
                subnet_id=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_SUBNET_ID,
                iam_instance_profile="",
            ),
            min_number_of_instances=num_to_start,
            number_of_instances=num_to_start,
            max_total_number_of_instances=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES,
        )
    if unneeded_instances:
        await ec2_client.terminate_instances(unneeded_instances)
        for instance in unneeded_instances:
            current_warm_buffer_pools[instance.type].remove_instance(instance)

    # 4. pull docker images if needed
    instances_to_stop: set[EC2InstanceData] = set()
    broken_instances_to_terminate: set[EC2InstanceData] = set()
    ssm_client = get_ssm_client(app)
    for warm_buffer_pool in current_warm_buffer_pools.values():
        if warm_buffer_pool.waiting_to_pull_instances:
            # trigger the image pulling
            await ec2_client.set_instances_tags(
                tuple(warm_buffer_pool.waiting_to_pull_instances),
                tags={_BUFFER_MACHINE_PULLING_EC2_TAG_KEY: AWSTagValue("true")},
            )
            ssm_command = await ssm_client.send_command(
                [
                    instance.id
                    for instance in warm_buffer_pool.waiting_to_pull_instances
                ],
                command="docker pull nginx:latest",
                command_name=_PREPULL_COMMAND_NAME,
            )
            await ec2_client.set_instances_tags(
                tuple(warm_buffer_pool.waiting_to_pull_instances),
                tags={
                    _BUFFER_MACHINE_PULLING_COMMAND_ID_EC2_TAG_KEY: AWSTagValue(
                        ssm_command.command_id
                    ),
                },
            )
        # wait for the image pulling to complete
        for instance in warm_buffer_pool.pulling_instances:
            if ssm_command_id := instance.tags.get(
                _BUFFER_MACHINE_PULLING_COMMAND_ID_EC2_TAG_KEY
            ):
                ssm_command = await ssm_client.get_command(
                    instance.id, command_id=ssm_command_id
                )
                match ssm_command.status:
                    case "Success":
                        instances_to_stop.add(instance)
                    case "Pending" | "InProgress":
                        pass
                    case _:
                        _logger.error(
                            "image pulling on buffer failed: %s",
                            f"{ssm_command.status}: {ssm_command.message}",
                        )
                        broken_instances_to_terminate.add(instance)

    if instances_to_stop:
        with log_context(
            _logger,
            logging.INFO,
            "pending buffer instances completed pulling of images, stopping them",
        ):

            tag_keys_to_remove = (
                _BUFFER_MACHINE_PULLING_EC2_TAG_KEY,
                _BUFFER_MACHINE_PULLING_COMMAND_ID_EC2_TAG_KEY,
            )
            await ec2_client.remove_instances_tags(
                tuple(instances_to_stop),
                tag_keys=tag_keys_to_remove,
            )
            await ec2_client.stop_instances(instances_to_stop)
    if broken_instances_to_terminate:
        with log_context(
            _logger,
            logging.WARNING,
            "pending buffer instances failed to pull images, terminating them",
        ):
            await ec2_client.terminate_instances(broken_instances_to_terminate)
