""" Free helper functions for AWS API

"""

import time
from textwrap import dedent

from .core.settings import AwsSettings


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
    # TODO: translate to aioboto https://github.com/terrycain/aioboto3
    user_data = compose_user_data(settings)

    ec2Client = boto3.client(
        "ec2",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name="us-east-1",
    )
    ec2Resource = boto3.resource("ec2", region_name="us-east-1")
    ec2 = boto3.resource("ec2", region_name="us-east-1")
    # TODO check bug on the auto-terminate ?
    # Create the instance
    instanceDict = ec2.create_instances(
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
    )
    instanceDict = instanceDict[0]
    print(
        "New instance launched for "
        + service_type
        + " services. Estimated time to launch and join the cluster : 2mns"
    )
    print("Pausing for 10mns before next check")
    time.sleep(600)
    # print("Instance state: %s" % instanceDict.state)
    # print("Public dns: %s" % instanceDict.public_dns_name)
    # print("Instance id: %s" % instanceDict.id)
