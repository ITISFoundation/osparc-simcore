# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
import random
from typing import Iterator

import botocore.exceptions
import pytest
from aiohttp.test_utils import unused_port
from faker import Faker
from moto.server import ThreadedMotoServer
from pydantic import ByteSize
from pytest_simcore.helpers.utils_docker import get_localhost_ip
from pytest_simcore.helpers.utils_envs import EnvVarsDict
from simcore_service_autoscaling.core.errors import Ec2InstanceNotFoundError
from simcore_service_autoscaling.core.settings import AwsSettings
from simcore_service_autoscaling.models import Resources
from simcore_service_autoscaling.utils_aws import (
    EC2Instance,
    _compose_user_data,
    closest_instance_policy,
    ec2_client,
    find_best_fitting_ec2_instance,
    get_ec2_instance_capabilities,
    start_instance_aws,
)


@pytest.fixture(scope="module")
def mocked_aws_server() -> Iterator[ThreadedMotoServer]:
    """creates a moto-server that emulates AWS services in place
    NOTE: Never use a bucket with underscores it fails!!
    """
    server = ThreadedMotoServer(ip_address=get_localhost_ip(), port=unused_port())
    # pylint: disable=protected-access
    print(f"--> started mock AWS server on {server._ip_address}:{server._port}")
    print(
        f"--> Dashboard available on [http://{server._ip_address}:{server._port}/moto-api/]"
    )
    server.start()
    yield server
    server.stop()
    print(f"<-- stopped mock AWS server on {server._ip_address}:{server._port}")


@pytest.fixture
def mocked_aws_server_envs(
    mocked_aws_server: ThreadedMotoServer, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    monkeypatch.setenv(
        "AWS_ENDPOINT",
        f"http://{mocked_aws_server._ip_address}:{mocked_aws_server._port}",  # pylint: disable=protected-access
    )
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "xxx")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "xxx")

    yield


@pytest.fixture
def aws_vpc_id(
    mocked_aws_server_envs: None,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[str]:
    settings = AwsSettings.create_from_envs()
    with ec2_client(settings) as client:
        vpc = client.create_vpc(
            CidrBlock="10.0.0.0/16",
        )
    vpc_id = vpc["Vpc"]["VpcId"]
    print(f"--> Created Vpc in AWS with {vpc_id=}")
    monkeypatch.setenv("AWS_VPC_ID", vpc_id)
    yield vpc_id

    with ec2_client(settings) as client:
        client.delete_vpc(VpcId=vpc_id)
        print(f"<-- Deleted Vpc in AWS with {vpc_id=}")


@pytest.fixture
def aws_subnet_id(
    mocked_aws_server_envs: None,
    monkeypatch: pytest.MonkeyPatch,
    aws_vpc_id: str,
) -> Iterator[str]:
    settings = AwsSettings.create_from_envs()
    with ec2_client(settings) as client:
        subnet = client.create_subnet(CidrBlock="10.0.1.0/24", VpcId=aws_vpc_id)
        subnet_id = subnet["Subnet"]["SubnetId"]
        print(f"--> Created Subnet in AWS with {subnet_id=}")

    monkeypatch.setenv("AWS_SUBNET_ID", subnet_id)
    yield subnet_id
    with ec2_client(settings) as client:
        client.delete_subnet(SubnetId=subnet_id)
        print(f"<-- Deleted Subnet in AWS with {subnet_id=}")


@pytest.fixture
def aws_security_group_id(
    mocked_aws_server_envs: None,
    monkeypatch: pytest.MonkeyPatch,
    faker: Faker,
    aws_vpc_id: str,
) -> Iterator[str]:
    settings = AwsSettings.create_from_envs()
    with ec2_client(settings) as client:
        security_group = client.create_security_group(
            Description=faker.text(), GroupName=faker.pystr(), VpcId=aws_vpc_id
        )
        security_group_id = security_group["GroupId"]
        print(f"--> Created Security Group in AWS with {security_group_id=}")
    monkeypatch.setenv("AWS_SECURITY_GROUP_IDS", json.dumps([security_group_id]))
    yield security_group_id
    with ec2_client(settings) as client:
        client.delete_security_group(GroupId=security_group_id)
        print(f"<-- Deleted Security Group in AWS with {security_group_id=}")


def test_ec2_client(
    app_environment: EnvVarsDict,
):
    settings = AwsSettings.create_from_envs()
    with ec2_client(settings) as client:
        ...

    with pytest.raises(
        botocore.exceptions.ClientError, match=r".+ AWS was not able to validate .+"
    ):
        with ec2_client(settings) as client:
            client.describe_account_attributes(DryRun=True)


def test_ec2_client_with_mock_server(
    app_environment: EnvVarsDict,
    mocked_aws_server_envs: None,
):
    settings = AwsSettings.create_from_envs()
    # passes without exception
    with ec2_client(settings) as client:
        client.describe_account_attributes(DryRun=True)


def test_get_ec2_instance_capabilities(
    app_environment: EnvVarsDict,
    mocked_aws_server_envs: None,
):
    settings = AwsSettings.create_from_envs()
    instance_types = get_ec2_instance_capabilities(settings)
    assert instance_types
    assert len(instance_types) == len(settings.AWS_EC2_TYPE_NAMES)

    # all the instance names are found and valid
    assert all(i.name in settings.AWS_EC2_TYPE_NAMES for i in instance_types)
    for instance_type_name in settings.AWS_EC2_TYPE_NAMES:
        assert any(i.name == instance_type_name for i in instance_types)


def test_find_best_fitting_ec2_instance_with_no_instances_raises():
    # this shall raise as there are no available instances
    with pytest.raises(Ec2InstanceNotFoundError):
        find_best_fitting_ec2_instance(
            available_ec2_instances=[],
            resources=Resources(cpus=0, ram=ByteSize(0)),
        )


@pytest.fixture
def random_fake_available_instances(faker: Faker) -> list[EC2Instance]:
    list_of_instances = [
        EC2Instance(
            name=faker.pystr(),
            cpus=n,
            ram=ByteSize(n),
        )
        for n in range(1, 30)
    ]
    random.shuffle(list_of_instances)
    return list_of_instances


def test_find_best_fitting_ec2_instance_closest_instance_policy_with_resource_0_raises(
    random_fake_available_instances: list[EC2Instance],
):
    with pytest.raises(Ec2InstanceNotFoundError):
        find_best_fitting_ec2_instance(
            available_ec2_instances=random_fake_available_instances,
            resources=Resources(cpus=0, ram=ByteSize(0)),
            score_type=closest_instance_policy,
        )


@pytest.mark.parametrize(
    "needed_resources,expected_ec2_instance",
    [
        (
            Resources(cpus=n, ram=ByteSize(n)),
            EC2Instance(name="fake", cpus=n, ram=ByteSize(n)),
        )
        for n in range(1, 30)
    ],
)
def test_find_best_fitting_ec2_instance_closest_instance_policy(
    needed_resources: Resources,
    expected_ec2_instance: EC2Instance,
    random_fake_available_instances: list[EC2Instance],
):
    found_instance: EC2Instance = find_best_fitting_ec2_instance(
        available_ec2_instances=random_fake_available_instances,
        resources=needed_resources,
        score_type=closest_instance_policy,
    )

    assert found_instance.dict(exclude={"name"}) == expected_ec2_instance.dict(
        exclude={"name"}
    )


def test_compose_user_data(app_environment: EnvVarsDict):
    settings = AwsSettings.create_from_envs()

    user_data = _compose_user_data(settings)
    print(user_data)

    for line in user_data.split("\n"):
        if "ssh" in line:
            assert f"ubuntu@{settings.AWS_DNS}" in line


def test_start_instance_aws(
    app_environment: EnvVarsDict,
    mocked_aws_server_envs: None,
    aws_subnet_id: None,
    aws_security_group_id: None,
    faker: Faker,
):
    settings = AwsSettings.create_from_envs()
    start_instance_aws(settings, faker.pystr(), tags=faker.pylist(allowed_types=(str,)))
