# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Any, Awaitable, Callable, Iterator, Mapping
from unittest import mock

import aiodocker
import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.generated_models.docker_rest_api import Node, ObjectVersion
from pydantic import ByteSize, parse_obj_as
from pytest_mock.plugin import MockerFixture
from simcore_service_autoscaling.core.settings import ApplicationSettings
from simcore_service_autoscaling.dynamic_scaling_core import check_dynamic_resources
from simcore_service_autoscaling.modules.docker import get_docker_client
from simcore_service_autoscaling.modules.ec2 import EC2InstanceData, get_ec2_client
from types_aiobotocore_ec2.client import EC2Client


@pytest.fixture
def mock_terminate_aws_instance(mocker: MockerFixture) -> Iterator[mock.Mock]:
    mocked_terminate_instance = mocker.patch(
        "simcore_service_autoscaling.modules.ec2.AutoscalingEC2.terminate_instance",
        autospec=True,
    )
    yield mocked_terminate_instance


@pytest.fixture
def mock_start_aws_instance(
    mocker: MockerFixture, ec2_instance_data: EC2InstanceData
) -> Iterator[mock.Mock]:
    mocked_start_aws_instance = mocker.patch(
        "simcore_service_autoscaling.modules.ec2.AutoscalingEC2.start_aws_instance",
        autospec=True,
        return_value=ec2_instance_data,
    )
    yield mocked_start_aws_instance


@pytest.fixture
def fake_node(faker: Faker) -> Node:
    return Node(
        ID=faker.uuid4(),
        Version=ObjectVersion(Index=faker.pyint()),
        CreatedAt=faker.date_time().isoformat(),
        UpdatedAt=faker.date_time().isoformat(),
    )


@pytest.fixture
def mock_wait_for_node(mocker: MockerFixture, fake_node: Node) -> Iterator[mock.Mock]:
    mocked_wait_for_node = mocker.patch(
        "simcore_service_autoscaling.dynamic_scaling_core.utils_docker.wait_for_node",
        autospec=True,
        return_value=fake_node,
    )
    yield mocked_wait_for_node


@pytest.fixture
def mock_tag_node(mocker: MockerFixture) -> Iterator[mock.Mock]:
    mocked_tag_node = mocker.patch(
        "simcore_service_autoscaling.dynamic_scaling_core.utils_docker.tag_node",
        autospec=True,
    )
    yield mocked_tag_node


@pytest.fixture
def minimal_configuration(
    docker_swarm: None,
    disabled_rabbitmq: None,
    disable_dynamic_service_background_task: None,
    aws_subnet_id: str,
    aws_security_group_id: str,
    aws_ami_id: str,
    aws_allowed_ec2_instance_type_names: list[str],
) -> Iterator[None]:
    yield


async def test_check_dynamic_resources_with_no_services_does_nothing(
    minimal_configuration: None,
    initialized_app: FastAPI,
    mock_start_aws_instance: mock.Mock,
    mock_terminate_aws_instance: mock.Mock,
):
    await check_dynamic_resources(initialized_app)
    mock_start_aws_instance.assert_not_called()
    mock_terminate_aws_instance.assert_not_called()


async def test_check_dynamic_resources_with_service_with_too_much_resources_starts_nothing(
    minimal_configuration: None,
    async_docker_client: aiodocker.Docker,
    initialized_app: FastAPI,
    create_service: Callable[
        [dict[str, Any], dict[str, Any], str], Awaitable[Mapping[str, Any]]
    ],
    task_template: dict[str, Any],
    create_task_reservations: Callable[[int, int], dict[str, Any]],
    mock_start_aws_instance: mock.Mock,
    mock_terminate_aws_instance: mock.Mock,
):
    task_template_with_too_many_resource = task_template | create_task_reservations(
        1000, 0
    )
    service_with_too_many_resources = await create_service(
        task_template_with_too_many_resource, {}, "pending"
    )

    await check_dynamic_resources(initialized_app)
    mock_start_aws_instance.assert_not_called()
    mock_terminate_aws_instance.assert_not_called()


async def test_check_dynamic_resources_with_pending_resources_starts_r5n_4xlarge_instance(
    minimal_configuration: None,
    app_settings: ApplicationSettings,
    async_docker_client: aiodocker.Docker,
    initialized_app: FastAPI,
    create_service: Callable[
        [dict[str, Any], dict[str, Any], str], Awaitable[Mapping[str, Any]]
    ],
    task_template: dict[str, Any],
    create_task_reservations: Callable[[int, int], dict[str, Any]],
    mock_start_aws_instance: mock.Mock,
    mock_terminate_aws_instance: mock.Mock,
    mock_wait_for_node: mock.Mock,
    mock_tag_node: mock.Mock,
    aws_instance_private_dns: str,
    fake_node: Node,
):
    """In this test we start on the host (1 node), start a service that needs
    resources that can be covered by a r5n_4x_large ec2 instance"""
    task_template_for_r5n_4x_large_with_256Gib = (
        task_template | create_task_reservations(4, parse_obj_as(ByteSize, "128GiB"))
    )
    service_with_too_many_resources = await create_service(
        task_template_for_r5n_4x_large_with_256Gib, {}, "pending"
    )

    await check_dynamic_resources(initialized_app)
    # we expect a new instance to be started
    mock_start_aws_instance.assert_called_once_with(
        get_ec2_client(initialized_app),
        app_settings.AUTOSCALING_EC2_INSTANCES,
        instance_type="r5n.4xlarge",
        tags=mock.ANY,
        startup_script=mock.ANY,
    )
    # after the instance has booted, then we wait for the node to appear in the swarm
    mock_wait_for_node.assert_called_once_with(
        get_docker_client(initialized_app),
        aws_instance_private_dns[: aws_instance_private_dns.find(".")],
    )
    # once the instance is in the swarm it shall be tagged as such
    mock_tag_node.assert_called_once_with(
        get_docker_client(initialized_app), fake_node, tags=mock.ANY, available=True
    )
    # there shall be no termination
    mock_terminate_aws_instance.assert_not_called()


async def test_check_dynamic_resources_with_pending_resources_actually_starts_new_instances(
    minimal_configuration: None,
    async_docker_client: aiodocker.Docker,
    initialized_app: FastAPI,
    create_service: Callable[
        [dict[str, Any], dict[str, Any], str], Awaitable[Mapping[str, Any]]
    ],
    task_template: dict[str, Any],
    create_task_reservations: Callable[[int, int], dict[str, Any]],
    ec2_client: EC2Client,
    mock_wait_for_node: mock.Mock,
    mock_tag_node: mock.Mock,
    fake_node: Node,
):
    """same test as above but with moto mocked server"""
    # we have nothing running now
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]

    task_template_for_r5n_8x_large_with_256Gib = (
        task_template | create_task_reservations(4, parse_obj_as(ByteSize, "128GiB"))
    )
    _service_with_too_many_resources = await create_service(
        task_template_for_r5n_8x_large_with_256Gib, {}, "pending"
    )

    await check_dynamic_resources(initialized_app)

    # check that the instances are really started
    all_instances = await ec2_client.describe_instances()
    assert len(all_instances["Reservations"]) == 1
    running_instance = all_instances["Reservations"][0]
    assert "Instances" in running_instance
    assert len(running_instance["Instances"]) == 1
    running_instance = running_instance["Instances"][0]
    assert "InstanceType" in running_instance
    assert running_instance["InstanceType"] == "r5n.4xlarge"
    assert "PrivateDnsName" in running_instance
    instance_private_dns_name = running_instance["PrivateDnsName"]
    assert instance_private_dns_name.endswith(".ec2.internal")

    mock_wait_for_node.assert_called_once_with(
        get_docker_client(initialized_app),
        instance_private_dns_name[: instance_private_dns_name.find(".")],
    )
    mock_tag_node.assert_called_once_with(
        get_docker_client(initialized_app), fake_node, tags=mock.ANY, available=True
    )
