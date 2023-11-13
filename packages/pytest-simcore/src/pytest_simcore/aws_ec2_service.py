# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import

import contextlib
import datetime
import random
from collections.abc import AsyncIterator, Callable
from typing import cast

import aioboto3
import pytest
from aiobotocore.session import ClientCreatorContext
from aws_library.ec2.models import EC2InstanceData, Resources
from faker import Faker
from pydantic import ByteSize
from settings_library.ec2 import EC2Settings
from types_aiobotocore_ec2.client import EC2Client


@pytest.fixture
async def ec2_client(
    mocked_ec2_server_settings: EC2Settings,
) -> AsyncIterator[EC2Client]:
    session = aioboto3.Session()
    exit_stack = contextlib.AsyncExitStack()
    session_client = session.client(
        "ec2",
        endpoint_url=mocked_ec2_server_settings.EC2_ENDPOINT,
        aws_access_key_id=mocked_ec2_server_settings.EC2_ACCESS_KEY_ID,
        aws_secret_access_key=mocked_ec2_server_settings.EC2_SECRET_ACCESS_KEY,
        region_name=mocked_ec2_server_settings.EC2_REGION_NAME,
    )
    assert isinstance(session_client, ClientCreatorContext)
    ec2_client = cast(EC2Client, await exit_stack.enter_async_context(session_client))

    yield ec2_client

    await exit_stack.aclose()


@pytest.fixture(scope="session")
def vpc_cidr_block() -> str:
    return "10.0.0.0/16"


@pytest.fixture
async def aws_vpc_id(
    ec2_client: EC2Client,
    vpc_cidr_block: str,
) -> AsyncIterator[str]:
    vpc = await ec2_client.create_vpc(
        CidrBlock=vpc_cidr_block,
    )
    vpc_id = vpc["Vpc"]["VpcId"]  # type: ignore
    print(f"--> Created Vpc in AWS with {vpc_id=}")
    yield vpc_id

    await ec2_client.delete_vpc(VpcId=vpc_id)
    print(f"<-- Deleted Vpc in AWS with {vpc_id=}")


@pytest.fixture(scope="session")
def subnet_cidr_block() -> str:
    return "10.0.1.0/24"


@pytest.fixture
async def aws_subnet_id(
    aws_vpc_id: str,
    ec2_client: EC2Client,
    subnet_cidr_block: str,
) -> AsyncIterator[str]:
    subnet = await ec2_client.create_subnet(
        CidrBlock=subnet_cidr_block, VpcId=aws_vpc_id
    )
    assert "Subnet" in subnet
    assert "SubnetId" in subnet["Subnet"]
    subnet_id = subnet["Subnet"]["SubnetId"]
    print(f"--> Created Subnet in AWS with {subnet_id=}")

    yield subnet_id

    # all the instances in the subnet must be terminated before that works
    instances_in_subnet = await ec2_client.describe_instances(
        Filters=[{"Name": "subnet-id", "Values": [subnet_id]}]
    )
    if instances_in_subnet["Reservations"]:
        print(f"--> terminating {len(instances_in_subnet)} instances in subnet")
        await ec2_client.terminate_instances(
            InstanceIds=[
                instance["Instances"][0]["InstanceId"]  # type: ignore
                for instance in instances_in_subnet["Reservations"]
            ]
        )
        print(f"<-- terminated {len(instances_in_subnet)} instances in subnet")

    await ec2_client.delete_subnet(SubnetId=subnet_id)
    subnets = await ec2_client.describe_subnets()
    print(f"<-- Deleted Subnet in AWS with {subnet_id=}")
    print(f"current {subnets=}")


@pytest.fixture
async def aws_security_group_id(
    faker: Faker,
    aws_vpc_id: str,
    ec2_client: EC2Client,
) -> AsyncIterator[str]:
    security_group = await ec2_client.create_security_group(
        Description=faker.text(), GroupName=faker.pystr(), VpcId=aws_vpc_id
    )
    security_group_id = security_group["GroupId"]
    print(f"--> Created Security Group in AWS with {security_group_id=}")
    yield security_group_id
    await ec2_client.delete_security_group(GroupId=security_group_id)
    print(f"<-- Deleted Security Group in AWS with {security_group_id=}")


@pytest.fixture
async def aws_ami_id(
    ec2_client: EC2Client,
) -> str:
    images = await ec2_client.describe_images()
    image = random.choice(images["Images"])  # noqa: S311
    assert "ImageId" in image
    return image["ImageId"]


@pytest.fixture
def fake_ec2_instance_data(faker: Faker) -> Callable[..., EC2InstanceData]:
    def _creator(**overrides) -> EC2InstanceData:
        return EC2InstanceData(
            **(
                {
                    "launch_time": faker.date_time(tzinfo=datetime.timezone.utc),
                    "id": faker.uuid4(),
                    "aws_private_dns": f"ip-{faker.ipv4().replace('.', '-')}.ec2.internal",
                    "aws_public_ip": faker.ipv4(),
                    "type": faker.pystr(),
                    "state": faker.pystr(),
                    "resources": Resources(cpus=4.0, ram=ByteSize(1024 * 1024)),
                    "tags": faker.pydict(allowed_types=(str,)),
                }
                | overrides
            )
        )

    return _creator
