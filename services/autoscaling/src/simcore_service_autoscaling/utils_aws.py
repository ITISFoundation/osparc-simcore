""" Free helper functions for AWS API

"""

import logging
import time
from datetime import datetime
from textwrap import dedent
from typing import Final

import boto3

from .core.settings import AwsSettings

logger = logging.getLogger(__name__)


AWS_EC2: Final = [
    {"name": "t2.xlarge", "CPUs": 4, "RAM": 16},
    {"name": "t2.2xlarge", "CPUs": 8, "RAM": 32},
    {"name": "r5n.4xlarge", "CPUs": 16, "RAM": 128},
    {"name": "r5n.8xlarge", "CPUs": 32, "RAM": 256},
]

ALL_AWS_EC2: Final = (
    [
        {"name": "t2.nano", "CPUs": 1, "RAM": 0.5},
        {"name": "t2.micro", "CPUs": 1, "RAM": 1},
        {"name": "t2.small", "CPUs": 1, "RAM": 2},
        {"name": "t2.medium", "CPUs": 2, "RAM": 4},
        {"name": "t2.large", "CPUs": 2, "RAM": 8},
    ]
    + AWS_EC2
    + [
        {"name": "r5n.12xlarge", "CPUs": 48, "RAM": 384},
        {"name": "r5n.16xlarge", "CPUs": 64, "RAM": 512},
        {"name": "r5n.24xlarge", "CPUs": 96, "RAM": 768},
    ]
)


def compose_user_data(settings: AwsSettings) -> str:
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


def start_instance_aws(ami_id, instance_type, tag, service_type, settings: AwsSettings):
    user_data = compose_user_data(settings)

    ec2_client = boto3.client(
        "ec2",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name="us-east-1",
    )

    ec2 = boto3.resource("ec2", region_name="us-east-1")

    instance = ec2.create_instances(
        ImageId=ami_id,
        KeyName=settings.AWS_KEY_NAME,
        InstanceType=instance_type,
        SecurityGroupIds=settings.AWS_SECURITY_GROUP_IDS,  # Have to be parametrized
        MinCount=1,
        MaxCount=1,
        InstanceInitiatedShutdownBehavior="terminate",
        SubnetId=settings.AWS_SUBNET_ID,  # Have to be parametrized
        TagSpecifications=[
            {"ResourceType": "instance", "Tags": [{"Key": "Name", "Value": tag}]}
        ],
        UserData=user_data,
    )[0]

    logger.debug(
        "New instance launched for %s services. Estimated time to launch and join the cluster : 2mns",
        service_type,
    )
    logger.debug("Pausing for 10mns before next check")

    time.sleep(600)
    logger.debug("Instance state: %s", instance.state)
    logger.debug("Public dns: %s", instance.public_dns_name)
    logger.debug("Instance id: %s", instance.id)

    return instance


def scale_up(CPUs, RAM, settings: AwsSettings):
    print("Processing the new instance on AWS..")

    # Has to be disccused
    for host in AWS_EC2:
        if host["CPUs"] >= CPUs and host["RAM"] >= RAM:
            new_host = host

    # Do we pass our scaling limits ?
    # if total_worker_CPUs + host["CPUs"] >= int(env.str("MAX_CPUs_CLUSTER")) or total_worker_RAM + host["RAM"] >= int(env.str("MAX_RAM_CLUSTER")):
    #    print("Error : We would pass the defined cluster limits in term of RAM/CPUs. We can't scale up")
    # else:

    now = datetime.utcnow()
    dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
    user_data = compose_user_data(settings)

    user_data += dedent(
        """\
    "docker node update --label-add sidecar=true $label"
    reboot_hour=$(last reboot | head -1 | awk '{print $8}')
    reboot_mn="${reboot_hour: -2}"
    if [ $reboot_mn -gt 4 ]
    then
            cron_mn=$((${reboot_mn} - 5))
    else
            cron_mn=55
    fi
    echo ${cron_mn}
    cron_mn+=" * * * * /home/ubuntu/cron_terminate.bash"
    cron_mn="*/10 * * * * /home/ubuntu/cron_terminate.bash"
    echo "${cron_mn}"
    (crontab -u ubuntu -l; echo "$cron_mn" ) | crontab -u ubuntu -
    """
    )

    start_instance_aws(
        "ami-0699f9dc425967eba",
        "t2.2xlarge",
        "Autoscaling node " + dt_string,
        "computational",
        user_data,
    )
