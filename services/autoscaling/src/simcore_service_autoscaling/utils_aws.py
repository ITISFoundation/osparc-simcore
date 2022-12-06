""" Free helper functions for AWS API

"""

import contextlib
import logging
from collections import OrderedDict
from textwrap import dedent
from typing import AsyncIterator, Callable, cast

import aioboto3
from pydantic import ByteSize, parse_obj_as
from servicelib.logging_utils import log_context
from types_aiobotocore_ec2 import EC2Client
from types_aiobotocore_ec2.literals import InstanceTypeType
from types_aiobotocore_ec2.type_defs import ReservationTypeDef

from .core.errors import (
    ConfigurationError,
    Ec2InstanceNotFoundError,
    Ec2TooManyInstancesError,
)
from .core.settings import EC2InstancesSettings, EC2Settings
from .models import EC2Instance, Resources

logger = logging.getLogger(__name__)


@contextlib.asynccontextmanager
async def ec2_client(settings: EC2Settings) -> AsyncIterator[EC2Client]:
    ec2 = None
    try:
        session = aioboto3.Session()
        async with session.client(
            "ec2",
            endpoint_url=settings.EC2_ENDPOINT,
            aws_access_key_id=settings.EC2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.EC2_SECRET_ACCESS_KEY,
            region_name=settings.EC2_REGION_NAME,
        ) as ec2:
            yield ec2
    finally:
        if ec2:
            await ec2.close()


async def get_ec2_instance_capabilities(
    settings: EC2Settings, instance_settings: EC2InstancesSettings
) -> list[EC2Instance]:
    async with ec2_client(settings) as ec2:
        instance_types = await ec2.describe_instance_types(
            InstanceTypes=cast(
                list[InstanceTypeType], instance_settings.EC2_INSTANCES_ALLOWED_TYPES
            )
        )

    list_instances: list[EC2Instance] = []
    for instance in instance_types.get("InstanceTypes", []):
        with contextlib.suppress(KeyError):
            list_instances.append(
                EC2Instance(
                    name=instance["InstanceType"],
                    cpus=instance["VCpuInfo"]["DefaultVCpus"],
                    ram=parse_obj_as(
                        ByteSize, f"{instance['MemoryInfo']['SizeInMiB']}MiB"
                    ),
                )
            )
    return list_instances


def closest_instance_policy(
    ec2_instance: EC2Instance,
    resources: Resources,
) -> float:
    if ec2_instance.cpus < resources.cpus or ec2_instance.ram < resources.ram:
        return 0
    # compute a score for all the instances that are above expectations
    # best is the exact ec2 instance
    cpu_ratio = float(ec2_instance.cpus - resources.cpus) / float(ec2_instance.cpus)
    ram_ratio = float(ec2_instance.ram - resources.ram) / float(ec2_instance.ram)
    return 100 * (1.0 - cpu_ratio) * (1.0 - ram_ratio)


def find_best_fitting_ec2_instance(
    allowed_ec2_instances: list[EC2Instance],
    resources: Resources,
    score_type: Callable[[EC2Instance, Resources], float] = closest_instance_policy,
) -> EC2Instance:
    if not allowed_ec2_instances:
        raise ConfigurationError(msg="allowed ec2 instances is missing!")
    score_to_ec2_candidate: dict[float, EC2Instance] = OrderedDict(
        sorted(
            {
                score_type(instance, resources): instance
                for instance in allowed_ec2_instances
            }.items(),
            reverse=True,
        )
    )

    score, instance = next(iter(score_to_ec2_candidate.items()))
    if score == 0:
        raise Ec2InstanceNotFoundError(
            needed_resources=resources, msg="no adequate EC2 instance found!"
        )
    return instance


def _compose_user_data(docker_join_bash_command: str) -> str:
    return dedent(
        f"""\
#!/bin/bash
{docker_join_bash_command}
"""
    )


def _is_ec2_instance_running(instance: ReservationTypeDef):
    return (
        instance.get("Instances", [{}])[0].get("State", {}).get("Name", "not_running")
        == "running"
    )


InstancePrivateDNSName = str


async def start_aws_instance(
    settings: EC2Settings,
    instance_settings: EC2InstancesSettings,
    instance_type: InstanceTypeType,
    tags: dict[str, str],
    startup_script: str,
) -> InstancePrivateDNSName:
    with log_context(
        logger,
        logging.INFO,
        msg=f"launching AWS instance {instance_type} with {tags=}",
    ):
        async with ec2_client(settings) as client:
            # first check the max amount is not already reached
            if current_instances := await client.describe_instances(
                Filters=[
                    {"Name": "tag-key", "Values": [tag_key]} for tag_key in tags.keys()
                ]
            ):
                if (
                    len(current_instances.get("Reservations", []))
                    >= instance_settings.EC2_INSTANCES_MAX_INSTANCES
                ) and all(
                    _is_ec2_instance_running(instance)
                    for instance in current_instances["Reservations"]
                ):
                    raise Ec2TooManyInstancesError(
                        num_instances=instance_settings.EC2_INSTANCES_MAX_INSTANCES
                    )

            instances = await client.run_instances(
                ImageId=instance_settings.EC2_INSTANCES_AMI_ID,
                MinCount=1,
                MaxCount=1,
                InstanceType=instance_type,
                InstanceInitiatedShutdownBehavior="terminate",
                KeyName=instance_settings.EC2_INSTANCES_KEY_NAME,
                SubnetId=instance_settings.EC2_INSTANCES_SUBNET_ID,
                TagSpecifications=[
                    {
                        "ResourceType": "instance",
                        "Tags": [
                            {"Key": tag_key, "Value": tag_value}
                            for tag_key, tag_value in tags.items()
                        ],
                    }
                ],
                UserData=_compose_user_data(startup_script),
                SecurityGroupIds=instance_settings.EC2_INSTANCES_SECURITY_GROUP_IDS,
            )
            instance_id = instances["Instances"][0]["InstanceId"]
            logger.info(
                "New instance launched: %s, waiting for it to start now...", instance_id
            )
            # wait for the instance to be in a running state
            # NOTE: reference to EC2 states https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html
            waiter = client.get_waiter("instance_exists")
            await waiter.wait(InstanceIds=[instance_id])
            logger.info(
                "instance %s exists now, waiting for running state...", instance_id
            )

            waiter = client.get_waiter("instance_running")
            await waiter.wait(InstanceIds=[instance_id])
            logger.info("instance %s is now running", instance_id)

            # NOTE: this is currently disactivated as this makes starting an instance
            # take between 2-4 minutes more and it seems to be responsive much before
            # nevertheless if we get weird errors, this should be activated again!

            # waiter = client.get_waiter("instance_status_ok")
            # await waiter.wait(InstanceIds=[instance_id])
            # logger.info("instance %s status is OK...", instance_id)

            # get the private IP
            instances = await client.describe_instances(InstanceIds=[instance_id])
            private_dns_name: str = instances["Reservations"][0]["Instances"][0][
                "PrivateDnsName"
            ]
            logger.info(
                "instance %s is available on %s, happy computing!!",
                instance_id,
                private_dns_name,
            )
            return private_dns_name
