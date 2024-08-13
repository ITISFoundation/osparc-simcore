"""Main entrypoint to manage buffer machines.

A buffer machine is a stopped pre-initialized EC2 instance with pre-pulled Docker images in its
EBS-based storage volume.

To create a ready buffer machine, one needs to first start the EC2 instance via EC2 API,
then via SSM api pull the Docker images to the EBS volume and finally stop the EC2 instance.

Open features:
    - handle changes in pre-pulled images (when the pre-pull images for a specific type changes),
    currently one needs to terminate all the buffer machines to get an upgrade,
    - use a cheap EC2 to prepare the buffer instead of the final instance type,
    - possibly copy already initialized EBS volumes, instead of pulling again,
    - possibly recycle de-activated EC2s instead of terminating them,
"""

import logging
from collections import defaultdict
from typing import Final, TypeAlias, cast

from aws_library.ec2 import (
    AWSTagKey,
    AWSTagValue,
    EC2InstanceConfig,
    EC2InstanceData,
    EC2InstanceType,
    Resources,
)
from aws_library.ssm import (
    SSMCommandExecutionResultError,
    SSMCommandExecutionTimeoutError,
)
from fastapi import FastAPI
from models_library.utils.json_serialization import json_dumps, json_loads
from pydantic import NonNegativeInt, parse_obj_as
from servicelib.logging_utils import log_context
from types_aiobotocore_ec2.literals import InstanceTypeType

from ..core.settings import get_application_settings
from ..models import BufferPool, BufferPoolManager
from ..utils.auto_scaling_core import ec2_buffer_startup_script
from ..utils.buffer_machines_pool_core import get_deactivated_buffer_ec2_tags
from .auto_scaling_mode_base import BaseAutoscaling
from .ec2 import get_ec2_client
from .ssm import get_ssm_client

_BUFFER_MACHINE_PULLING_EC2_TAG_KEY: Final[AWSTagKey] = parse_obj_as(
    AWSTagKey, "pulling"
)
_BUFFER_MACHINE_PULLING_COMMAND_ID_EC2_TAG_KEY: Final[AWSTagKey] = parse_obj_as(
    AWSTagKey, "ssm-command-id"
)
_PREPULL_COMMAND_NAME: Final[str] = "docker images pulling"
_PRE_PULLED_IMAGES_EC2_TAG_KEY: Final[AWSTagKey] = parse_obj_as(
    AWSTagKey, "io.simcore.autoscaling.pre_pulled_images"
)


_logger = logging.getLogger(__name__)


async def _analyze_running_instance_state(
    app: FastAPI, *, buffer_pool: BufferPool, instance: EC2InstanceData
):
    ssm_client = get_ssm_client(app)

    if _BUFFER_MACHINE_PULLING_EC2_TAG_KEY in instance.tags:
        buffer_pool.pulling_instances.add(instance)
    elif await ssm_client.is_instance_connected_to_ssm_server(instance.id):
        app_settings = get_application_settings(app)
        assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
        try:
            if await ssm_client.wait_for_has_instance_completed_cloud_init(instance.id):
                if app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES[
                    instance.type
                ].pre_pull_images:
                    buffer_pool.waiting_to_pull_instances.add(instance)
                else:
                    buffer_pool.waiting_to_stop_instances.add(instance)
            else:
                buffer_pool.pending_instances.add(instance)
        except (
            SSMCommandExecutionResultError,
            SSMCommandExecutionTimeoutError,
        ):
            _logger.exception(
                "Unnexpected error when checking EC2 cloud initialization completion!. "
                "The machine will be terminated. TIP: check the initialization phase for errors."
            )
            buffer_pool.broken_instances.add(instance)


async def _analyse_current_state(
    app: FastAPI, *, auto_scaling_mode: BaseAutoscaling
) -> BufferPoolManager:
    ec2_client = get_ec2_client(app)
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec

    all_buffer_instances = await ec2_client.get_instances(
        key_names=[app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_KEY_NAME],
        tags=get_deactivated_buffer_ec2_tags(app, auto_scaling_mode),
        state_names=["stopped", "pending", "running", "stopping"],
    )

    buffers_manager = BufferPoolManager()
    for instance in all_buffer_instances:
        match instance.state:
            case "stopped":
                buffers_manager.buffer_pools[instance.type].ready_instances.add(
                    instance
                )
            case "pending":
                buffers_manager.buffer_pools[instance.type].pending_instances.add(
                    instance
                )
            case "stopping":
                buffers_manager.buffer_pools[instance.type].stopping_instances.add(
                    instance
                )
            case "running":
                await _analyze_running_instance_state(
                    app,
                    buffer_pool=buffers_manager.buffer_pools[instance.type],
                    instance=instance,
                )

    _logger.info("Current buffer pools: %s", f"{buffers_manager}")
    return buffers_manager


async def _terminate_unneeded_pools(
    app: FastAPI,
    buffers_manager: BufferPoolManager,
) -> BufferPoolManager:
    ec2_client = get_ec2_client(app)
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    allowed_instance_types = set(
        app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES
    )
    if terminateable_warm_pool_types := set(buffers_manager.buffer_pools).difference(
        allowed_instance_types
    ):
        with log_context(
            _logger,
            logging.INFO,
            msg=f"removing unneeded buffer pools for '{terminateable_warm_pool_types}'",
        ):
            instances_to_terminate: set[EC2InstanceData] = set()
            for ec2_type in terminateable_warm_pool_types:
                instances_to_terminate = instances_to_terminate.union(
                    buffers_manager.buffer_pools[ec2_type].all_instances()
                )
            await ec2_client.terminate_instances(instances_to_terminate)
            for ec2_type in terminateable_warm_pool_types:
                buffers_manager.buffer_pools.pop(ec2_type)
    return buffers_manager


async def _terminate_instances_with_invalid_pre_pulled_images(
    app: FastAPI, buffers_manager: BufferPoolManager
) -> BufferPoolManager:
    ec2_client = get_ec2_client(app)
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    terminateable_instances = set()
    for (
        ec2_type,
        ec2_boot_config,
    ) in app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES.items():
        instance_type = cast(InstanceTypeType, ec2_type)
        all_pre_pulled_instances = buffers_manager.buffer_pools[
            instance_type
        ].pre_pulled_instances()

        for instance in all_pre_pulled_instances:
            if (
                pre_pulled_images := json_loads(
                    instance.tags.get(_PRE_PULLED_IMAGES_EC2_TAG_KEY, "[]")
                )
            ) and pre_pulled_images != ec2_boot_config.pre_pull_images:
                _logger.info(
                    "%s",
                    f"{instance.id=} has invalid {pre_pulled_images=}, expected is {ec2_boot_config.pre_pull_images=}",
                )
                terminateable_instances.add(instance)

    if terminateable_instances:
        await ec2_client.terminate_instances(terminateable_instances)
        for instance in terminateable_instances:
            buffers_manager.buffer_pools[instance.type].remove_instance(instance)
    return buffers_manager


async def _terminate_broken_instances(
    app: FastAPI, buffers_manager: BufferPoolManager
) -> BufferPoolManager:
    ec2_client = get_ec2_client(app)
    termineatable_instances = set()
    for pool in buffers_manager.buffer_pools.values():
        termineatable_instances.update(pool.broken_instances)
    if termineatable_instances:
        await ec2_client.terminate_instances(termineatable_instances)
        for instance in termineatable_instances:
            buffers_manager.buffer_pools[instance.type].remove_instance(instance)
    return buffers_manager


async def _add_remove_buffer_instances(
    app: FastAPI,
    buffers_manager: BufferPoolManager,
    *,
    auto_scaling_mode: BaseAutoscaling,
) -> BufferPoolManager:
    ec2_client = get_ec2_client(app)
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec

    # let's find what is missing and what is not needed
    missing_instances: dict[InstanceTypeType, NonNegativeInt] = defaultdict(int)
    unneeded_instances: set[EC2InstanceData] = set()
    for (
        ec2_type,
        ec2_boot_config,
    ) in app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES.items():
        instance_type = cast(InstanceTypeType, ec2_type)
        all_pool_instances = buffers_manager.buffer_pools[instance_type].all_instances()
        if len(all_pool_instances) < ec2_boot_config.buffer_count:
            missing_instances[instance_type] += ec2_boot_config.buffer_count - len(
                all_pool_instances
            )
        else:
            terminateable_instances = set(
                list(all_pool_instances)[ec2_boot_config.buffer_count :]
            )
            unneeded_instances = unneeded_instances.union(terminateable_instances)

    for ec2_type, num_to_start in missing_instances.items():
        ec2_boot_specific = (
            app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES[ec2_type]
        )
        await ec2_client.launch_instances(
            EC2InstanceConfig(
                type=EC2InstanceType(
                    name=ec2_type,
                    resources=Resources.create_as_empty(),  # fake resources
                ),
                tags=get_deactivated_buffer_ec2_tags(app, auto_scaling_mode),
                startup_script=ec2_buffer_startup_script(
                    ec2_boot_specific, app_settings
                ),
                ami_id=ec2_boot_specific.ami_id,
                key_name=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_KEY_NAME,
                security_group_ids=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_SECURITY_GROUP_IDS,
                subnet_id=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_SUBNET_ID,
                iam_instance_profile=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ATTACHED_IAM_PROFILE,
            ),
            min_number_of_instances=num_to_start,
            number_of_instances=num_to_start,
            max_total_number_of_instances=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES,
        )
    if unneeded_instances:
        await ec2_client.terminate_instances(unneeded_instances)
        for instance in unneeded_instances:
            buffers_manager.buffer_pools[instance.type].remove_instance(instance)
    return buffers_manager


InstancesToStop: TypeAlias = set[EC2InstanceData]
InstancesToTerminate: TypeAlias = set[EC2InstanceData]
_DOCKER_PULL_COMMAND: Final[
    str
] = "docker compose -f /docker-pull.compose.yml -p buffering pull"


async def _handle_pool_image_pulling(
    app: FastAPI, instance_type: InstanceTypeType, pool: BufferPool
) -> tuple[InstancesToStop, InstancesToTerminate]:
    ec2_client = get_ec2_client(app)
    ssm_client = get_ssm_client(app)
    if pool.waiting_to_pull_instances:
        # trigger the image pulling
        ssm_command = await ssm_client.send_command(
            [instance.id for instance in pool.waiting_to_pull_instances],
            command=_DOCKER_PULL_COMMAND,
            command_name=_PREPULL_COMMAND_NAME,
        )
        await ec2_client.set_instances_tags(
            tuple(pool.waiting_to_pull_instances),
            tags={
                _BUFFER_MACHINE_PULLING_EC2_TAG_KEY: AWSTagValue("true"),
                _BUFFER_MACHINE_PULLING_COMMAND_ID_EC2_TAG_KEY: AWSTagValue(
                    ssm_command.command_id
                ),
            },
        )

    instances_to_stop: set[EC2InstanceData] = pool.waiting_to_stop_instances
    broken_instances_to_terminate: set[EC2InstanceData] = set()
    # wait for the image pulling to complete
    for instance in pool.pulling_instances:
        if ssm_command_id := instance.tags.get(
            _BUFFER_MACHINE_PULLING_COMMAND_ID_EC2_TAG_KEY
        ):
            ssm_command = await ssm_client.get_command(
                instance.id, command_id=ssm_command_id
            )
            match ssm_command.status:
                case "Success":
                    instances_to_stop.add(instance)
                case "InProgress" | "Pending":
                    # do nothing we pass
                    pass
                case _:
                    _logger.error(
                        "image pulling on buffer failed: %s",
                        f"{ssm_command.status}: {ssm_command.message}",
                    )
                    broken_instances_to_terminate.add(instance)
    if instances_to_stop:
        app_settings = get_application_settings(app)
        assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
        await ec2_client.set_instances_tags(
            tuple(instances_to_stop),
            tags={
                _PRE_PULLED_IMAGES_EC2_TAG_KEY: AWSTagValue(
                    json_dumps(
                        app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES[
                            instance_type
                        ].pre_pull_images
                    )
                )
            },
        )
    return instances_to_stop, broken_instances_to_terminate


async def _handle_image_pre_pulling(
    app: FastAPI, buffers_manager: BufferPoolManager
) -> None:
    ec2_client = get_ec2_client(app)
    instances_to_stop: set[EC2InstanceData] = set()
    broken_instances_to_terminate: set[EC2InstanceData] = set()
    for instance_type, pool in buffers_manager.buffer_pools.items():
        (
            pool_instances_to_stop,
            pool_instances_to_terminate,
        ) = await _handle_pool_image_pulling(app, instance_type, pool)
        instances_to_stop.update(pool_instances_to_stop)
        broken_instances_to_terminate.update(pool_instances_to_terminate)
    # 5. now stop and terminate if necessary
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
            _logger, logging.WARNING, "broken buffer instances, terminating them"
        ):
            await ec2_client.terminate_instances(broken_instances_to_terminate)


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

    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec

    # 1. Analyze the current state by type
    buffers_manager = await _analyse_current_state(
        app, auto_scaling_mode=auto_scaling_mode
    )
    # 2. Terminate unneeded warm pools (e.g. if the user changed the allowed instance types)
    buffers_manager = await _terminate_unneeded_pools(app, buffers_manager)

    buffers_manager = await _terminate_instances_with_invalid_pre_pulled_images(
        app, buffers_manager
    )
    # 3. terminate broken instances
    buffers_manager = await _terminate_broken_instances(app, buffers_manager)

    # 3. add/remove buffer instances base on ec2 boot specific data
    buffers_manager = await _add_remove_buffer_instances(
        app, buffers_manager, auto_scaling_mode=auto_scaling_mode
    )

    # 4. pull docker images if needed
    await _handle_image_pre_pulling(app, buffers_manager)
