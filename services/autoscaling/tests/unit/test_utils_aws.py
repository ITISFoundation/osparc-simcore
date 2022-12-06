# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import random

import pytest
from faker import Faker
from pydantic import ByteSize
from pytest_simcore.helpers.utils_envs import EnvVarsDict
from simcore_service_autoscaling.core.errors import (
    ConfigurationError,
    Ec2InstanceNotFoundError,
    Ec2TooManyInstancesError,
)
from simcore_service_autoscaling.core.settings import ApplicationSettings
from simcore_service_autoscaling.models import Resources
from simcore_service_autoscaling.utils_aws import (
    EC2Client,
    EC2Instance,
    _compose_user_data,
    closest_instance_policy,
    find_best_fitting_ec2_instance,
    get_ec2_instance_capabilities,
    start_aws_instance,
)


@pytest.fixture
def app_settings(
    app_environment: EnvVarsDict,
) -> ApplicationSettings:
    return ApplicationSettings.create_from_envs()


async def test_get_ec2_instance_capabilities(
    mocked_aws_server_envs: None,
    aws_allowed_ec2_instance_type_names: list[str],
    app_settings: ApplicationSettings,
    ec2_client: EC2Client,
):
    assert app_settings.AUTOSCALING_EC2_ACCESS
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    instance_types = await get_ec2_instance_capabilities(
        ec2_client, app_settings.AUTOSCALING_EC2_INSTANCES
    )
    assert instance_types
    assert len(instance_types) == len(
        app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES
    )

    # all the instance names are found and valid
    assert all(
        i.name in app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES
        for i in instance_types
    )
    for (
        instance_type_name
    ) in app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES:
        assert any(i.name == instance_type_name for i in instance_types)


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
    user_data = _compose_user_data(command)
    assert user_data.startswith("#!/bin/bash")
    assert command in user_data


async def test_start_aws_instance(
    mocked_aws_server_envs: None,
    aws_vpc_id: str,
    aws_subnet_id: str,
    aws_security_group_id: str,
    aws_ami_id: str,
    ec2_client: EC2Client,
    app_settings: ApplicationSettings,
    faker: Faker,
):
    assert app_settings.AUTOSCALING_EC2_ACCESS
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    # we have nothing running now in ec2
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]

    instance_type = faker.pystr()
    tags = faker.pydict(allowed_types=(str,))
    startup_script = faker.pystr()
    await start_aws_instance(
        ec2_client,
        app_settings.AUTOSCALING_EC2_INSTANCES,
        instance_type,
        tags=tags,
        startup_script=startup_script,
    )

    # check we have that now in ec2
    all_instances = await ec2_client.describe_instances()
    assert len(all_instances["Reservations"]) == 1
    running_instance = all_instances["Reservations"][0]
    assert "Instances" in running_instance
    assert len(running_instance["Instances"]) == 1
    running_instance = running_instance["Instances"][0]
    assert "InstanceType" in running_instance
    assert running_instance["InstanceType"] == instance_type
    assert "Tags" in running_instance
    assert running_instance["Tags"] == [
        {"Key": key, "Value": value} for key, value in tags.items()
    ]


async def test_start_aws_instance_is_limited_in_number_of_instances(
    mocked_aws_server_envs: None,
    aws_vpc_id: str,
    aws_subnet_id: str,
    aws_security_group_id: str,
    aws_ami_id: str,
    ec2_client: EC2Client,
    app_settings: ApplicationSettings,
    faker: Faker,
):
    assert app_settings.AUTOSCALING_EC2_ACCESS
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    # we have nothing running now in ec2
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]

    # create as many instances as we can
    tags = faker.pydict(allowed_types=(str,))
    startup_script = faker.pystr()
    for _ in range(app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES):
        await start_aws_instance(
            ec2_client,
            app_settings.AUTOSCALING_EC2_INSTANCES,
            faker.pystr(),
            tags=tags,
            startup_script=startup_script,
        )

    # now creating one more shall fail
    with pytest.raises(Ec2TooManyInstancesError):
        await start_aws_instance(
            ec2_client,
            app_settings.AUTOSCALING_EC2_INSTANCES,
            faker.pystr(),
            tags=tags,
            startup_script=startup_script,
        )
