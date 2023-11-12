# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import

import contextlib
import random
from collections.abc import AsyncIterator, Iterator
from typing import cast

import aioboto3
import pytest
import requests
from aiobotocore.session import ClientCreatorContext
from aiohttp.test_utils import unused_port
from faker import Faker
from moto.server import ThreadedMotoServer
from settings_library.ec2 import EC2Settings
from types_aiobotocore_ec2.client import EC2Client

from .helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from .helpers.utils_host import get_localhost_ip


@pytest.fixture(scope="module")
def mocked_aws_server() -> Iterator[ThreadedMotoServer]:
    """creates a moto-server that emulates AWS services in place
    NOTE: Never use a bucket with underscores it fails!!
    """
    server = ThreadedMotoServer(ip_address=get_localhost_ip(), port=unused_port())
    # pylint: disable=protected-access
    print(
        f"--> started mock AWS server on {server._ip_address}:{server._port}"  # noqa: SLF001
    )
    print(
        f"--> Dashboard available on [http://{server._ip_address}:{server._port}/moto-api/]"  # noqa: SLF001
    )
    server.start()
    yield server
    server.stop()
    print(
        f"<-- stopped mock AWS server on {server._ip_address}:{server._port}"  # noqa: SLF001
    )


@pytest.fixture
def reset_aws_server_state(mocked_aws_server: ThreadedMotoServer) -> Iterator[None]:
    # NOTE: reset_aws_server_state [http://docs.getmoto.org/en/latest/docs/server_mode.html#reset-api]
    yield
    # pylint: disable=protected-access
    requests.post(
        f"http://{mocked_aws_server._ip_address}:{mocked_aws_server._port}/moto-api/reset",  # noqa: SLF001
        timeout=10,
    )
    print(
        f"<-- cleaned mock AWS server on {mocked_aws_server._ip_address}:{mocked_aws_server._port}"  # noqa: SLF001
    )


@pytest.fixture
def mocked_ec2_server_settings(
    mocked_aws_server: ThreadedMotoServer,
    reset_aws_server_state: None,
) -> EC2Settings:
    return EC2Settings(
        EC2_ACCESS_KEY_ID="xxx",
        EC2_ENDPOINT=f"http://{mocked_aws_server._ip_address}:{mocked_aws_server._port}",  # pylint: disable=protected-access # noqa: SLF001
        EC2_SECRET_ACCESS_KEY="xxx",  # noqa: S106
    )


@pytest.fixture
def mocked_ec2_server_envs(
    mocked_ec2_server_settings: EC2Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    changed_envs: EnvVarsDict = mocked_ec2_server_settings.dict()
    return setenvs_from_dict(monkeypatch, changed_envs)


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
