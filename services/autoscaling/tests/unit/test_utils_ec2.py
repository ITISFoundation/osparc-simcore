# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import Callable

import pytest
from aws_library.ec2 import EC2InstanceType, Resources
from aws_library.ec2._models import EC2InstanceData
from faker import Faker
from pydantic import ByteSize
from simcore_service_autoscaling.core.errors import (
    ConfigurationError,
    Ec2InvalidDnsNameError,
    TaskBestFittingInstanceNotFoundError,
)
from simcore_service_autoscaling.utils.utils_ec2 import (
    closest_instance_policy,
    compose_user_data,
    find_best_fitting_ec2_instance,
    node_host_name_from_ec2_private_dns,
    node_ip_from_ec2_private_dns,
)


async def test_find_best_fitting_ec2_instance_with_no_instances_raises():
    # this shall raise as there are no available instances
    with pytest.raises(ConfigurationError):
        find_best_fitting_ec2_instance(
            allowed_ec2_instances=[],
            resources=Resources(cpus=0, ram=ByteSize(0)),
        )


async def test_find_best_fitting_ec2_instance_closest_instance_policy_with_resource_0_raises(
    random_fake_available_instances: list[EC2InstanceType],
):
    with pytest.raises(TaskBestFittingInstanceNotFoundError):
        find_best_fitting_ec2_instance(
            allowed_ec2_instances=random_fake_available_instances,
            resources=Resources(cpus=0, ram=ByteSize(0)),
            score_type=closest_instance_policy,
        )


@pytest.mark.parametrize(
    "needed_resources,expected_ec2_instance",
    [
        (
            Resources(cpus=n, ram=ByteSize(n)),
            EC2InstanceType(
                name="c5ad.12xlarge", resources=Resources(cpus=n, ram=ByteSize(n))
            ),
        )
        for n in range(1, 30)
    ],
    ids=str,
)
async def test_find_best_fitting_ec2_instance_closest_instance_policy(
    needed_resources: Resources,
    expected_ec2_instance: EC2InstanceType,
    random_fake_available_instances: list[EC2InstanceType],
):
    found_instance: EC2InstanceType = find_best_fitting_ec2_instance(
        allowed_ec2_instances=random_fake_available_instances,
        resources=needed_resources,
        score_type=closest_instance_policy,
    )

    assert found_instance.resources == expected_ec2_instance.resources


def test_compose_user_data(faker: Faker):
    command = faker.text()
    user_data = compose_user_data(command)
    assert user_data.startswith("#!/bin/bash")
    assert command in user_data


@pytest.mark.parametrize(
    "aws_private_dns, expected_host_name",
    [
        ("ip-10-12-32-3.internal-data", "ip-10-12-32-3"),
        ("ip-10-12-32-32.internal-data", "ip-10-12-32-32"),
        ("ip-10-0-3-129.internal-data", "ip-10-0-3-129"),
        ("ip-10-0-3-12.internal-data", "ip-10-0-3-12"),
    ],
)
def test_node_host_name_from_ec2_private_dns(
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
    aws_private_dns: str,
    expected_host_name: str,
):
    instance = fake_ec2_instance_data(
        aws_private_dns=aws_private_dns,
    )
    assert node_host_name_from_ec2_private_dns(instance) == expected_host_name


def test_node_host_name_from_ec2_private_dns_raises_with_invalid_name(
    fake_ec2_instance_data: Callable[..., EC2InstanceData], faker: Faker
):
    instance = fake_ec2_instance_data(aws_private_dns=faker.name())
    with pytest.raises(Ec2InvalidDnsNameError):
        node_host_name_from_ec2_private_dns(instance)


@pytest.mark.parametrize(
    "aws_private_dns, expected_host_name",
    [
        ("ip-10-12-32-3.internal-data", "10.12.32.3"),
        ("ip-10-12-32-32.internal-data", "10.12.32.32"),
        ("ip-10-0-3-129.internal-data", "10.0.3.129"),
        ("ip-10-0-3-12.internal-data", "10.0.3.12"),
    ],
)
def test_node_ip_from_ec2_private_dns(
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
    aws_private_dns: str,
    expected_host_name: str,
):
    instance = fake_ec2_instance_data(
        aws_private_dns=aws_private_dns,
    )
    assert node_ip_from_ec2_private_dns(instance) == expected_host_name


def test_node_ip_from_ec2_private_dns_raises_with_invalid_name(
    fake_ec2_instance_data: Callable[..., EC2InstanceData], faker: Faker
):
    instance = fake_ec2_instance_data(aws_private_dns=faker.name())
    with pytest.raises(Ec2InvalidDnsNameError):
        node_ip_from_ec2_private_dns(instance)
