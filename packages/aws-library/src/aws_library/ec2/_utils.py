from textwrap import dedent
from typing import TYPE_CHECKING, cast

from types_aiobotocore_ec2.type_defs import InstanceTypeDef

from ._models import EC2InstanceData, EC2Tags

if TYPE_CHECKING:
    from ._client import SimcoreEC2API


def compose_user_data(docker_join_bash_command: str) -> str:
    return dedent(
        f"""\
#!/bin/bash
{docker_join_bash_command}
"""
    )


async def ec2_instance_data_from_aws_instance(
    ec2_client: "SimcoreEC2API",
    instance: InstanceTypeDef,
) -> EC2InstanceData:
    assert "LaunchTime" in instance  # nosec
    assert "InstanceId" in instance  # nosec
    assert "PrivateDnsName" in instance  # nosec
    assert "InstanceType" in instance  # nosec
    assert "State" in instance  # nosec
    assert "Name" in instance["State"]  # nosec
    ec2_instance_types = await ec2_client.get_ec2_instance_capabilities(
        {instance["InstanceType"]}
    )
    assert len(ec2_instance_types) == 1  # nosec
    assert "Tags" in instance  # nosec
    return EC2InstanceData(
        launch_time=instance["LaunchTime"],
        id=instance["InstanceId"],
        aws_private_dns=instance["PrivateDnsName"],
        aws_public_ip=instance.get("PublicIpAddress", None),
        type=instance["InstanceType"],
        state=instance["State"]["Name"],
        resources=ec2_instance_types[0].resources,
        tags=cast(EC2Tags, {tag["Key"]: tag["Value"] for tag in instance["Tags"]}),
    )
