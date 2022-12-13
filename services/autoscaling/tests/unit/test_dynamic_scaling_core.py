# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import datetime
from typing import Any, AsyncIterator, Awaitable, Callable, Iterator
from unittest import mock

import aiodocker
import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.docker import DockerLabelKey
from models_library.generated_models.docker_rest_api import (
    Node,
    ObjectVersion,
    Service,
    Task,
)
from pydantic import ByteSize, parse_obj_as
from pytest_mock.plugin import MockerFixture
from simcore_service_autoscaling.core.settings import ApplicationSettings
from simcore_service_autoscaling.dynamic_scaling_core import (
    _find_terminateable_nodes,
    _mark_empty_active_nodes_to_drain,
    _try_scale_down_cluster,
    _try_scale_up_with_drained_nodes,
    check_dynamic_resources,
)
from simcore_service_autoscaling.modules.docker import (
    AutoscalingDocker,
    get_docker_client,
)
from simcore_service_autoscaling.modules.ec2 import EC2InstanceData
from types_aiobotocore_ec2.client import EC2Client


@pytest.fixture
def mock_terminate_instance(mocker: MockerFixture) -> Iterator[mock.Mock]:
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
def mock_get_running_instance(
    mocker: MockerFixture, ec2_instance_data: EC2InstanceData
) -> Iterator[mock.Mock]:
    mocked_start_aws_instance = mocker.patch(
        "simcore_service_autoscaling.modules.ec2.AutoscalingEC2.get_running_instance",
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
        "simcore_service_autoscaling.utils.utils_docker.tag_node",
        autospec=True,
    )
    yield mocked_tag_node


@pytest.fixture
def mock_remove_nodes(mocker: MockerFixture) -> Iterator[mock.Mock]:
    mocked_tag_node = mocker.patch(
        "simcore_service_autoscaling.utils.utils_docker.remove_nodes",
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
    mock_terminate_instance: mock.Mock,
):
    await check_dynamic_resources(initialized_app)
    mock_start_aws_instance.assert_not_called()
    mock_terminate_instance.assert_not_called()


async def test_check_dynamic_resources_with_service_with_too_much_resources_starts_nothing(
    minimal_configuration: None,
    service_monitored_labels: dict[DockerLabelKey, str],
    initialized_app: FastAPI,
    create_service: Callable[
        [dict[str, Any], dict[DockerLabelKey, str], str], Awaitable[Service]
    ],
    task_template: dict[str, Any],
    create_task_reservations: Callable[[int, int], dict[str, Any]],
    mock_start_aws_instance: mock.Mock,
    mock_terminate_instance: mock.Mock,
):
    task_template_with_too_many_resource = task_template | create_task_reservations(
        1000, 0
    )
    await create_service(
        task_template_with_too_many_resource,
        service_monitored_labels,
        "pending",
    )

    await check_dynamic_resources(initialized_app)
    mock_start_aws_instance.assert_not_called()
    mock_terminate_instance.assert_not_called()


async def test_check_dynamic_resources_with_pending_resources_starts_new_instances(
    minimal_configuration: None,
    service_monitored_labels: dict[DockerLabelKey, str],
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    create_service: Callable[
        [dict[str, Any], dict[DockerLabelKey, str], str], Awaitable[Service]
    ],
    task_template: dict[str, Any],
    create_task_reservations: Callable[[int, int], dict[str, Any]],
    ec2_client: EC2Client,
    mock_wait_for_node: mock.Mock,
    mock_tag_node: mock.Mock,
    fake_node: Node,
):
    # we have nothing running now
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]

    # create a task that needs more power
    task_template_for_r5n_8x_large_with_256Gib = (
        task_template | create_task_reservations(4, parse_obj_as(ByteSize, "128GiB"))
    )
    await create_service(
        task_template_for_r5n_8x_large_with_256Gib,
        service_monitored_labels,
        "pending",
    )

    # run the code
    await check_dynamic_resources(initialized_app)

    # check the instance was started and we have exactly 1
    all_instances = await ec2_client.describe_instances()
    assert len(all_instances["Reservations"]) == 1
    running_instance = all_instances["Reservations"][0]
    assert "Instances" in running_instance
    assert len(running_instance["Instances"]) == 1
    running_instance = running_instance["Instances"][0]
    assert "InstanceType" in running_instance
    assert running_instance["InstanceType"] == "r5n.4xlarge"
    assert "Tags" in running_instance
    assert running_instance["Tags"]
    expected_tag_keys = [
        "io.simcore.autoscaling.version",
        "io.simcore.autoscaling.monitored_nodes_labels",
        "io.simcore.autoscaling.monitored_services_labels",
    ]
    for tag_dict in running_instance["Tags"]:
        assert "Key" in tag_dict
        assert "Value" in tag_dict

        assert tag_dict["Key"] in expected_tag_keys

    assert "PrivateDnsName" in running_instance
    instance_private_dns_name = running_instance["PrivateDnsName"]
    assert instance_private_dns_name.endswith(".ec2.internal")

    # expect to wait for the node to appear
    mock_wait_for_node.assert_called_once_with(
        get_docker_client(initialized_app),
        instance_private_dns_name[: instance_private_dns_name.find(".")],
    )

    # expect to tag the node with the expected labels, and also to make it active
    assert app_settings.AUTOSCALING_NODES_MONITORING
    expected_docker_node_tags = {
        tag_key: "true"
        for tag_key in (
            app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS
            + app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NEW_NODES_LABELS
        )
    }
    mock_tag_node.assert_called_once_with(
        get_docker_client(initialized_app),
        fake_node,
        tags=expected_docker_node_tags,
        available=True,
    )


async def test__mark_empty_active_nodes_to_drain(
    minimal_configuration: None,
    initialized_app: FastAPI,
    host_node: Node,
    mock_tag_node: mock.Mock,
):
    # since we have no service running, we expect the passed node to be set to drain
    await _mark_empty_active_nodes_to_drain(initialized_app, [host_node])
    mock_tag_node.assert_called_once_with(mock.ANY, host_node, tags={}, available=False)


async def test__mark_empty_active_nodes_to_drain_when_services_running_are_missing_labels(
    minimal_configuration: None,
    initialized_app: FastAPI,
    host_node: Node,
    mock_tag_node: mock.Mock,
    create_service: Callable[
        [dict[str, Any], dict[DockerLabelKey, str], str], Awaitable[Service]
    ],
    task_template: dict[str, Any],
    create_task_reservations: Callable[[int, int], dict[str, Any]],
    host_cpu_count: int,
):
    # create a service that runs without task labels
    task_template_that_runs = task_template | create_task_reservations(
        int(host_cpu_count / 2 + 1), 0
    )
    await create_service(
        task_template_that_runs,
        {},
        "running",
    )

    await _mark_empty_active_nodes_to_drain(initialized_app, [host_node])
    mock_tag_node.assert_called_once_with(mock.ANY, host_node, tags={}, available=False)


async def test__mark_empty_active_nodes_to_drain_does_not_drain_if_service_is_running_with_correct_labels(
    minimal_configuration: None,
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    host_node: Node,
    mock_tag_node: mock.Mock,
    create_service: Callable[
        [dict[str, Any], dict[DockerLabelKey, str], str], Awaitable[Service]
    ],
    task_template: dict[str, Any],
    create_task_reservations: Callable[[int, int], dict[str, Any]],
    service_monitored_labels: dict[DockerLabelKey, str],
    host_cpu_count: int,
):
    # create a service that runs without task labels
    task_template_that_runs = task_template | create_task_reservations(
        int(host_cpu_count / 2 + 1), 0
    )
    assert app_settings.AUTOSCALING_NODES_MONITORING
    await create_service(
        task_template_that_runs,
        service_monitored_labels,
        "running",
    )

    # since we have no service running, we expect the passed node to be set to drain
    await _mark_empty_active_nodes_to_drain(initialized_app, [host_node])
    mock_tag_node.assert_not_called()


async def test__find_terminateable_nodes_with_no_hosts(
    minimal_configuration: None,
    initialized_app: FastAPI,
    host_node: Node,
):
    # there is no node to terminate, since the host is not an EC2 instance and is not drained
    assert await _find_terminateable_nodes(initialized_app, [host_node]) == []


async def test__find_terminateable_nodes_with_drained_host_but_not_in_ec2(
    minimal_configuration: None,
    initialized_app: FastAPI,
    drained_host_node: Node,
):
    # there is no node to terminate, since the host is not an EC2 instance
    assert await _find_terminateable_nodes(initialized_app, [drained_host_node]) == []


async def test__find_terminateable_nodes_with_drained_host_and_in_ec2(
    minimal_configuration: None,
    initialized_app: FastAPI,
    drained_host_node: Node,
    mock_get_running_instance: mock.Mock,
    ec2_instance_data: EC2InstanceData,
    app_settings: ApplicationSettings,
):
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    assert (
        app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
        > datetime.timedelta(seconds=10)
    ), "this tests relies on the fact that the time before termination is above 10 seconds"

    # if the instance started just about now, then it should not be terminateable
    ec2_instance_data.launch_time = datetime.datetime.utcnow().replace(
        tzinfo=datetime.timezone.utc
    )
    assert await _find_terminateable_nodes(initialized_app, [drained_host_node]) == []
    mock_get_running_instance.assert_called_once_with(
        mock.ANY,
        app_settings.AUTOSCALING_EC2_INSTANCES,
        tag_keys=["io.simcore.autoscaling.version"],
        instance_host_name=mock.ANY,
    )
    mock_get_running_instance.reset_mock()

    # if the instance started just after the termination time, even on several days, it is not terminateable
    ec2_instance_data.launch_time = (
        datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
        - app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
        - datetime.timedelta(days=21)
        + datetime.timedelta(seconds=10)
    )

    assert await _find_terminateable_nodes(initialized_app, [drained_host_node]) == []
    mock_get_running_instance.assert_called_once_with(
        mock.ANY,
        app_settings.AUTOSCALING_EC2_INSTANCES,
        tag_keys=["io.simcore.autoscaling.version"],
        instance_host_name=mock.ANY,
    )
    mock_get_running_instance.reset_mock()

    # if the instance started just before the termination time, even on several days, it is terminateable
    ec2_instance_data.launch_time = (
        datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
        - app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
        - datetime.timedelta(days=21)
        - datetime.timedelta(seconds=10)
    )

    assert await _find_terminateable_nodes(initialized_app, [drained_host_node]) == [
        (drained_host_node, ec2_instance_data)
    ]
    mock_get_running_instance.assert_called_once_with(
        mock.ANY,
        app_settings.AUTOSCALING_EC2_INSTANCES,
        tag_keys=["io.simcore.autoscaling.version"],
        instance_host_name=mock.ANY,
    )


async def test__try_scale_down_cluster_with_no_nodes(
    minimal_configuration: None,
    initialized_app: FastAPI,
    mock_get_running_instance: mock.Mock,
    mock_remove_nodes: mock.Mock,
):
    # this shall work as is
    await _try_scale_down_cluster(initialized_app, [])
    mock_get_running_instance.assert_not_called()
    mock_remove_nodes.assert_not_called()


async def test__try_scale_down_cluster(
    minimal_configuration: None,
    initialized_app: FastAPI,
    drained_host_node: Node,
    mock_get_running_instance: mock.Mock,
    mock_terminate_instance: mock.Mock,
    mock_remove_nodes: mock.Mock,
    ec2_instance_data: EC2InstanceData,
    app_settings: ApplicationSettings,
):
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    assert (
        app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
        > datetime.timedelta(seconds=10)
    ), "this tests relies on the fact that the time before termination is above 10 seconds"

    ec2_instance_data.launch_time = (
        datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
        - app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
        - datetime.timedelta(days=21)
        - datetime.timedelta(seconds=10)
    )
    await _try_scale_down_cluster(initialized_app, [drained_host_node])
    mock_get_running_instance.assert_called_once()
    mock_terminate_instance.assert_called_once()
    mock_remove_nodes.assert_called_once()


async def test__try_scale_up_with_drained_nodes_with_no_tasks(
    minimal_configuration: None,
    initialized_app: FastAPI,
    host_node: Node,
    mock_tag_node: mock.Mock,
):
    # no tasks, does nothing and returns True
    assert await _try_scale_up_with_drained_nodes(initialized_app, [], []) is True
    assert (
        await _try_scale_up_with_drained_nodes(initialized_app, [host_node], []) is True
    )
    mock_tag_node.assert_not_called()


async def test__try_scale_up_with_drained_nodes_with_no_drained_nodes(
    minimal_configuration: None,
    autoscaling_docker: AutoscalingDocker,
    initialized_app: FastAPI,
    host_node: Node,
    mock_tag_node: mock.Mock,
    create_service: Callable[
        [dict[str, Any], dict[DockerLabelKey, str], str], Awaitable[Service]
    ],
    task_template: dict[str, Any],
    create_task_reservations: Callable[[int, int], dict[str, Any]],
    host_cpu_count: int,
):
    # task with no drain nodes returns False
    task_template_that_runs = task_template | create_task_reservations(
        int(host_cpu_count / 2 + 1), 0
    )
    service_with_no_reservations = await create_service(
        task_template_that_runs, {}, "running"
    )
    assert service_with_no_reservations.Spec
    service_tasks = parse_obj_as(
        list[Task],
        await autoscaling_docker.tasks.list(
            filters={"service": service_with_no_reservations.Spec.Name}
        ),
    )
    assert service_tasks
    assert len(service_tasks) == 1
    assert (
        await _try_scale_up_with_drained_nodes(
            initialized_app, [host_node], service_tasks
        )
        is False
    )
    mock_tag_node.assert_not_called()


@pytest.fixture
async def drained_host_node(
    host_node: Node, async_docker_client: aiodocker.Docker
) -> AsyncIterator[Node]:

    assert host_node.ID
    assert host_node.Version
    assert host_node.Version.Index
    assert host_node.Spec
    assert host_node.Spec.Availability
    assert host_node.Spec.Role

    old_availability = host_node.Spec.Availability
    await async_docker_client.nodes.update(
        node_id=host_node.ID,
        version=host_node.Version.Index,
        spec={
            "Availability": "drain",
            "Labels": host_node.Spec.Labels,
            "Role": host_node.Spec.Role.value,
        },
    )
    drained_node = parse_obj_as(
        Node, await async_docker_client.nodes.inspect(node_id=host_node.ID)
    )
    yield drained_node
    # revert
    # NOTE: getting the node again as the version might have changed
    drained_node = parse_obj_as(
        Node, await async_docker_client.nodes.inspect(node_id=host_node.ID)
    )
    assert drained_node.ID
    assert drained_node.Version
    assert drained_node.Version.Index
    assert drained_node.Spec
    assert drained_node.Spec.Role
    reverted_node = (
        await async_docker_client.nodes.update(
            node_id=drained_node.ID,
            version=drained_node.Version.Index,
            spec={
                "Availability": old_availability.value,
                "Labels": drained_node.Spec.Labels,
                "Role": drained_node.Spec.Role.value,
            },
        ),
    )


async def test__try_scale_up_with_drained_nodes_with_drained_node(
    minimal_configuration: None,
    autoscaling_docker: AutoscalingDocker,
    initialized_app: FastAPI,
    drained_host_node: Node,
    mock_tag_node: mock.Mock,
    create_service: Callable[
        [dict[str, Any], dict[DockerLabelKey, str], str], Awaitable[Service]
    ],
    task_template: dict[str, Any],
    create_task_reservations: Callable[[int, int], dict[str, Any]],
    host_cpu_count: int,
):
    # task with no drain nodes returns False
    task_template_that_runs = task_template | create_task_reservations(
        int(host_cpu_count / 2 + 1), 0
    )
    service_with_no_reservations = await create_service(
        task_template_that_runs, {}, "pending"
    )
    assert service_with_no_reservations.Spec
    service_tasks = parse_obj_as(
        list[Task],
        await autoscaling_docker.tasks.list(
            filters={"service": service_with_no_reservations.Spec.Name}
        ),
    )
    assert service_tasks
    assert len(service_tasks) == 1
    assert (
        await _try_scale_up_with_drained_nodes(
            initialized_app, [drained_host_node], service_tasks
        )
        is True
    )
    mock_tag_node.assert_called_once_with(
        mock.ANY, drained_host_node, tags={}, available=True
    )
