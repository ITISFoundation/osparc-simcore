# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import random

import botocore.exceptions
import pytest
from faker import Faker
from pydantic import ByteSize
from pytest_simcore.helpers.utils_envs import EnvVarsDict
from simcore_service_autoscaling.core.errors import (
    Ec2InstanceNotFoundError,
    Ec2TooManyInstancesError,
)
from simcore_service_autoscaling.core.settings import AwsSettings
from simcore_service_autoscaling.models import Resources
from simcore_service_autoscaling.utils_aws import (
    EC2Client,
    EC2Instance,
    _compose_user_data,
    closest_instance_policy,
    ec2_client,
    find_best_fitting_ec2_instance,
    get_ec2_instance_capabilities,
    start_aws_instance,
)


@pytest.fixture
def aws_settings(
    app_environment: EnvVarsDict,
) -> AwsSettings:
    return AwsSettings.create_from_envs()


def test_ec2_client(aws_settings: AwsSettings):
    with ec2_client(aws_settings) as client:
        ...

    with pytest.raises(
        botocore.exceptions.ClientError, match=r".+ AWS was not able to validate .+"
    ):
        with ec2_client(aws_settings) as client:
            client.describe_account_attributes(DryRun=True)


def test_ec2_client_with_mock_server(
    mocked_aws_server_envs: None, aws_settings: AwsSettings
):
    # passes without exception
    with ec2_client(aws_settings) as client:
        client.describe_account_attributes(DryRun=True)


def test_get_ec2_instance_capabilities(
    mocked_aws_server_envs: None,
    aws_allowed_ec2_instance_type_names: list[str],
    aws_settings: AwsSettings,
):
    instance_types = get_ec2_instance_capabilities(aws_settings)
    assert instance_types
    assert len(instance_types) == len(aws_settings.AWS_ALLOWED_EC2_INSTANCE_TYPE_NAMES)

    # all the instance names are found and valid
    assert all(
        i.name in aws_settings.AWS_ALLOWED_EC2_INSTANCE_TYPE_NAMES
        for i in instance_types
    )
    for instance_type_name in aws_settings.AWS_ALLOWED_EC2_INSTANCE_TYPE_NAMES:
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


def test_compose_user_data(aws_settings: AwsSettings):
    user_data = _compose_user_data(aws_settings)
    print(user_data)

    for line in user_data.split("\n"):
        if "ssh" in line:
            assert f"ubuntu@{aws_settings.AWS_DNS}" in line


def test_start_instance_aws(
    faker: Faker,
    mocked_ec2_server_with_client: EC2Client,
    aws_settings: AwsSettings,
):
    # we have nothing running now in ec2
    all_instances = mocked_ec2_server_with_client.describe_instances()
    assert not all_instances["Reservations"]

    instance_type = faker.pystr()
    tags = faker.pydict(allowed_types=(str,))
    start_aws_instance(aws_settings, instance_type, tags=tags)

    # check we have that now in ec2
    all_instances = mocked_ec2_server_with_client.describe_instances()
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


def test_start_aws_instance_is_limited_in_number_of_instances(
    mocked_ec2_server_with_client: EC2Client, aws_settings: AwsSettings, faker: Faker
):
    # we have nothing running now in ec2
    all_instances = mocked_ec2_server_with_client.describe_instances()
    assert not all_instances["Reservations"]

    # create as many instances as we can
    tags = faker.pydict(allowed_types=(str,))
    for _ in range(aws_settings.AWS_MAX_NUMBER_OF_INSTANCES):
        start_aws_instance(aws_settings, faker.pystr(), tags=tags)

    # now creating one more shall fail
    with pytest.raises(Ec2TooManyInstancesError):
        start_aws_instance(aws_settings, faker.pystr(), tags=tags)
