""" Free helper functions for AWS API

"""

import contextlib
import logging
import time
from dataclasses import dataclass
from textwrap import dedent
from typing import Iterator

import boto3
from mypy_boto3_ec2.client import EC2Client
from pydantic import ByteSize, parse_obj_as
from servicelib.logging_utils import log_context

from .core.errors import Ec2InstanceNotFoundError
from .core.settings import AwsSettings
from .models import Resources

logger = logging.getLogger(__name__)

# NOTE: Possible future improvement: Get this list programmatically instead of hardcoded
# SEE https://github.com/ITISFoundation/osparc-simcore/pull/3364#discussion_r987819879


@dataclass(frozen=True)
class EC2Instance:
    name: str
    cpus: int
    ram: float


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
            InstanceTypes=settings.AWS_EC2_TYPE_NAMES
        )

    list_instances: list[EC2Instance] = []
    for instance in instance_types.get("InstanceTypes", []):
        with contextlib.suppress(KeyError):
            list_instances.append(
                EC2Instance(
                    instance["InstanceType"],
                    cpus=instance["VCpuInfo"]["DefaultVCpus"],
                    ram=parse_obj_as(
                        ByteSize, f"{instance['MemoryInfo']['SizeInMiB']}MiB"
                    ),
                )
            )
    return list_instances


def find_needed_ec2_instance(
    available_ec2_instances: list[EC2Instance],
    resources: Resources,
) -> EC2Instance:
    def _default_policy(ec2_instance: EC2Instance) -> bool:
        return ec2_instance.cpus >= resources.cpus and ec2_instance.ram >= resources.ram

    ec2_candidates = [
        instance for instance in available_ec2_instances if _default_policy(instance)
    ]
    if not ec2_candidates:
        raise Ec2InstanceNotFoundError(needed_resources=resources)
    return ec2_candidates[0]


def compose_user_data(settings: AwsSettings) -> str:
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


def create_ec2_client(settings: AwsSettings):
    return boto3.client(
        "ec2",
        endpoint_url=settings.AWS_ENDPOINT,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION_NAME,
    )


def start_instance_aws(
    settings: AwsSettings,
    instance_type: str,
    tags: list[str],
):
    with log_context(
        logger,
        logging.DEBUG,
        msg=f"launching AWS instance {instance_type} with {tags=}",
    ):
        user_data = compose_user_data(settings)

        ec2 = boto3.resource("ec2", region_name="us-east-1")
        instance = ec2.create_instances(
            ImageId=settings.AWS_AMI_ID,
            KeyName=settings.AWS_KEY_NAME,
            InstanceType=instance_type,
            SecurityGroupIds=settings.AWS_SECURITY_GROUP_IDS,
            MinCount=1,
            MaxCount=1,
            InstanceInitiatedShutdownBehavior="terminate",
            SubnetId=settings.AWS_SUBNET_ID,
            TagSpecifications=[
                {
                    "ResourceType": "instance",
                    "Tags": [{"Key": "Name", "Value": tag} for tag in tags],
                }
            ],
            UserData=user_data,
        )[0]

    logger.debug(
        "New instance launched. Estimated time to launch and join the cluster : 2mns",
    )
    logger.debug("Pausing for 10mns before next check")

    time.sleep(600)
    logger.debug("Instance state: %s", instance.state)
    logger.debug("Public dns: %s", instance.public_dns_name)
    logger.debug("Instance id: %s", instance.id)

    return instance
