# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import random

import pytest
from faker import Faker
from pydantic import ByteSize
from simcore_service_autoscaling.core.errors import (
    ConfigurationError,
    Ec2InstanceNotFoundError,
)
from simcore_service_autoscaling.models import Resources
from simcore_service_autoscaling.utils.ec2 import (
    EC2Instance,
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


async def test_find_best_fitting_ec2_instance_closest_instance_policy_with_resource_0_raises(
    random_fake_available_instances: list[EC2Instance],
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
            EC2Instance(name="fake", cpus=n, ram=ByteSize(n)),
        )
        for n in range(1, 30)
    ],
)
async def test_find_best_fitting_ec2_instance_closest_instance_policy(
    needed_resources: Resources,
    expected_ec2_instance: EC2Instance,
    random_fake_available_instances: list[EC2Instance],
):
    found_instance: EC2Instance = find_best_fitting_ec2_instance(
        allowed_ec2_instances=random_fake_available_instances,
        resources=needed_resources,
        score_type=closest_instance_policy,
    )

    assert found_instance.dict(exclude={"name"}) == expected_ec2_instance.dict(
        exclude={"name"}
    )


def test_compose_user_data(faker: Faker):
    command = faker.text()
    user_data = compose_user_data(command)
    assert user_data.startswith("#!/bin/bash")
    assert command in user_data
