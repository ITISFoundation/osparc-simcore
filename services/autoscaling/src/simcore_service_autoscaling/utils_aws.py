""" Free helper functions for AWS API

"""

import contextlib
import logging
from collections import OrderedDict
from textwrap import dedent
from typing import Iterator

import boto3
from mypy_boto3_ec2.client import EC2Client
from mypy_boto3_ec2.type_defs import ReservationTypeDef
from pydantic import BaseModel, ByteSize, PositiveInt, parse_obj_as
from servicelib.logging_utils import log_context

from .core.errors import Ec2InstanceNotFoundError, Ec2TooManyInstancesError
from .core.settings import AwsSettings
from .models import Resources

logger = logging.getLogger(__name__)

# NOTE: Possible future improvement: Get this list programmatically instead of hardcoded
# SEE https://github.com/ITISFoundation/osparc-simcore/pull/3364#discussion_r987819879


class EC2Instance(BaseModel):
    name: str
    cpus: PositiveInt
    ram: ByteSize


@contextlib.contextmanager
def ec2_client(settings: AwsSettings) -> Iterator[EC2Client]:
    client = None
    try:
        client = boto3.client(
            "ec2",
            endpoint_url=settings.AWS_ENDPOINT,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION_NAME,
        )
        yield client
    finally:
        if client:
            client.close()


def get_ec2_instance_capabilities(settings: AwsSettings) -> list[EC2Instance]:
    with ec2_client(settings) as ec2:
        instance_types = ec2.describe_instance_types(
            InstanceTypes=settings.AWS_ALLOWED_EC2_INSTANCE_TYPE_NAMES
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
    available_ec2_instances: list[EC2Instance],
    resources: Resources,
    score_type=closest_instance_policy,
) -> EC2Instance:
    score_to_ec2_candidate: dict[float, EC2Instance] = OrderedDict(
        sorted(
            {
                score_type(instance, resources): instance
                for instance in available_ec2_instances
            }.items(),
            reverse=True,
        )
    )
    if not score_to_ec2_candidate:
        raise Ec2InstanceNotFoundError(needed_resources=resources)
    score, instance = next(iter(score_to_ec2_candidate.items()))
    if score == 0:
        raise Ec2InstanceNotFoundError(
            needed_resources=resources, msg="no adequate EC2 instance found!"
        )
    return instance


def _compose_user_data(settings: AwsSettings) -> str:
    # NOTE: docker swarm commands might be done with aioboto?
    # SEE https://github.com/ITISFoundation/osparc-simcore/pull/3364#discussion_r987820674
    return dedent(
        f"""\
    #!/bin/bash
    cd /home/ubuntu
    hostname=$(ssh -i {settings.AWS_KEY_NAME}.pem -oStrictHostKeyChecking=no ubuntu@{settings.AWS_DNS} "hostname" 2>&1)
    token=$(ssh -i {settings.AWS_KEY_NAME}.pem -oStrictHostKeyChecking=no ubuntu@{settings.AWS_DNS} "docker swarm join-token -q worker")
    host=$(ssh -i {settings.AWS_KEY_NAME}.pem -oStrictHostKeyChecking=no ubuntu@{settings.AWS_DNS} "docker swarm join-token worker" 2>&1)
    docker swarm join --token ${{token}} ${{host##* }}
    label=$(ssh -i {settings.AWS_KEY_NAME}.pem -oStrictHostKeyChecking=no ubuntu@{settings.AWS_DNS} "docker node ls | grep $(hostname)")
    label="$(cut -d' ' -f1 <<<"$label")"
    ssh -i {settings.AWS_KEY_NAME}.pem -oStrictHostKeyChecking=no ubuntu@{settings.AWS_DNS} "docker node update --label-add sidecar=true $label"
    ssh -i {settings.AWS_KEY_NAME}.pem -oStrictHostKeyChecking=no ubuntu@{settings.AWS_DNS} "docker node update --label-add standardworker=true $label"
    """
    )


def _is_ec2_instance_running(instance: ReservationTypeDef):
    return (
        instance.get("Instances", [{}])[0].get("State", {}).get("Name", "not_running")
        == "running"
    )


def start_aws_instance(
    settings: AwsSettings,
    instance_type: str,
    tags: dict[str, str],
):
    with log_context(
        logger,
        logging.DEBUG,
        msg=f"launching AWS instance {instance_type} with {tags=}",
    ), ec2_client(settings) as client:

        # first check the max amount is not already reached
        if current_instances := client.describe_instances(
            Filters=[
                {"Name": "tag-key", "Values": [tag_key]} for tag_key in tags.keys()
            ]
        ):
            if (
                len(current_instances.get("Reservations", []))
                >= settings.AWS_MAX_NUMBER_OF_INSTANCES
            ) and all(
                _is_ec2_instance_running(instance)
                for instance in current_instances["Reservations"]
            ):
                raise Ec2TooManyInstancesError(
                    num_instances=settings.AWS_MAX_NUMBER_OF_INSTANCES
                )

        user_data = _compose_user_data(settings)

        instances = client.run_instances(
            ImageId=settings.AWS_AMI_ID,
            MinCount=1,
            MaxCount=1,
            InstanceType=instance_type,
            InstanceInitiatedShutdownBehavior="terminate",
            KeyName=settings.AWS_KEY_NAME,
            SubnetId=settings.AWS_SUBNET_ID,
            TagSpecifications=[
                {
                    "ResourceType": "instance",
                    "Tags": [
                        {"Key": tag_key, "Value": tag_value}
                        for tag_key, tag_value in tags.items()
                    ],
                }
            ],
            UserData=user_data,
            SecurityGroupIds=settings.AWS_SECURITY_GROUP_IDS,
        )
        instance_id = instances["Instances"][0]["InstanceId"]
        logger.info(
            "New instance launched: %s, waiting for it to start now...", instance_id
        )
        waiter = client.get_waiter("instance_running")
        waiter.wait(InstanceIds=[instance_id])
        logger.info("instance %s is now running, happy computing...", instance_id)
