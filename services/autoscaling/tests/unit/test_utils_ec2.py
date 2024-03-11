# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from aws_library.ec2.models import EC2InstanceType, Resources
from faker import Faker
from pydantic import ByteSize
from simcore_service_autoscaling.core.errors import (
    ConfigurationError,
    Ec2InstanceNotFoundError,
)
from simcore_service_autoscaling.utils.utils_ec2 import (
    closest_instance_policy,
    compose_user_data,
    find_best_fitting_ec2_instance,
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
    with pytest.raises(Ec2InstanceNotFoundError):
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
