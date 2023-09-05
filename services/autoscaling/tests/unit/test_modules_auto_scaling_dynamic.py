# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import asyncio
import base64
import dataclasses
import datetime
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from dataclasses import dataclass
from typing import Any
from unittest import mock

import aiodocker
import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.docker import DockerLabelKey
from models_library.generated_models.docker_rest_api import Node, Service, Task
from models_library.rabbitmq_messages import RabbitAutoscalingStatusMessage
from pydantic import ByteSize, parse_obj_as
from pytest_mock.plugin import MockerFixture
from simcore_service_autoscaling.core.settings import ApplicationSettings
from simcore_service_autoscaling.models import AssociatedInstance, Cluster, Resources
from simcore_service_autoscaling.modules.auto_scaling_base import auto_scale_cluster
from simcore_service_autoscaling.modules.auto_scaling_dynamic import (
    _activate_drained_nodes,
    _deactivate_empty_nodes,
    _find_terminateable_instances,
    _try_scale_down_cluster,
    scale_cluster_with_labelled_services,
)
from simcore_service_autoscaling.modules.docker import (
    AutoscalingDocker,
    get_docker_client,
)
from simcore_service_autoscaling.modules.ec2 import EC2InstanceData
from types_aiobotocore_ec2.client import EC2Client


@pytest.fixture
def cluster() -> Callable[..., Cluster]:
    def _creator(**cluter_overrides) -> Cluster:
        return dataclasses.replace(
            Cluster(
                active_nodes=[],
                drained_nodes=[],
                reserve_drained_nodes=[],
                pending_ec2s=[],
                disconnected_nodes=[],
                terminated_instances=[],
            ),
            **cluter_overrides,
        )

    return _creator


@pytest.fixture
def mock_terminate_instances(mocker: MockerFixture) -> Iterator[mock.Mock]:
    return mocker.patch(
        "simcore_service_autoscaling.modules.ec2.AutoscalingEC2.terminate_instances",
        autospec=True,
    )


@pytest.fixture
def mock_start_aws_instance(
    mocker: MockerFixture,
    aws_instance_private_dns: str,
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
) -> Iterator[mock.Mock]:
    return mocker.patch(
        "simcore_service_autoscaling.modules.ec2.AutoscalingEC2.start_aws_instance",
        autospec=True,
        return_value=fake_ec2_instance_data(aws_private_dns=aws_instance_private_dns),
    )


@pytest.fixture
def mock_rabbitmq_post_message(mocker: MockerFixture) -> Iterator[mock.Mock]:
    return mocker.patch(
        "simcore_service_autoscaling.utils.rabbitmq.post_message", autospec=True
    )


@pytest.fixture
def mock_find_node_with_name(
    mocker: MockerFixture, fake_node: Node
) -> Iterator[mock.Mock]:
    return mocker.patch(
        "simcore_service_autoscaling.modules.auto_scaling_dynamic.utils_docker.find_node_with_name",
        autospec=True,
        return_value=fake_node,
    )


@pytest.fixture
def mock_tag_node(mocker: MockerFixture) -> mock.Mock:
    async def fake_tag_node(*args, **kwargs) -> Node:
        return args[1]

    return mocker.patch(
        "simcore_service_autoscaling.modules.auto_scaling_dynamic.utils_docker.tag_node",
        autospec=True,
        side_effect=fake_tag_node,
    )


@pytest.fixture
def mock_set_node_availability(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "simcore_service_autoscaling.modules.auto_scaling_dynamic.utils_docker.set_node_availability",
        autospec=True,
    )


@pytest.fixture
def mock_remove_nodes(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "simcore_service_autoscaling.modules.auto_scaling_dynamic.utils_docker.remove_nodes",
        autospec=True,
    )


@pytest.fixture
def mock_cluster_used_resources(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "simcore_service_autoscaling.modules.auto_scaling_dynamic.utils_docker.compute_cluster_used_resources",
        autospec=True,
        return_value=Resources.create_as_empty(),
    )


@pytest.fixture
def mock_compute_node_used_resources(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "simcore_service_autoscaling.modules.auto_scaling_dynamic.utils_docker.compute_node_used_resources",
        autospec=True,
        return_value=Resources.create_as_empty(),
    )


@pytest.fixture
def mock_machines_buffer(monkeypatch: pytest.MonkeyPatch) -> int:
    num_machines_in_buffer = 5
    monkeypatch.setenv("EC2_INSTANCES_MACHINES_BUFFER", f"{num_machines_in_buffer}")
    return num_machines_in_buffer


@pytest.fixture
def with_valid_time_before_termination(
    monkeypatch: pytest.MonkeyPatch,
) -> datetime.timedelta:
    time = "00:11:00"
    monkeypatch.setenv("EC2_INSTANCES_TIME_BEFORE_TERMINATION", time)
    return parse_obj_as(datetime.timedelta, time)


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
    await async_docker_client.nodes.update(
        node_id=drained_node.ID,
        version=drained_node.Version.Index,
        spec={
            "Availability": old_availability.value,
            "Labels": drained_node.Spec.Labels,
            "Role": drained_node.Spec.Role.value,
        },
    )


@pytest.fixture
def minimal_configuration(
    docker_swarm: None,
    disabled_rabbitmq: None,
    disable_dynamic_service_background_task: None,
    aws_subnet_id: str,
    aws_security_group_id: str,
    aws_ami_id: str,
    aws_allowed_ec2_instance_type_names: list[str],
    mocked_redis_server: None,
) -> None:
    ...


def _assert_rabbit_autoscaling_message_sent(
    mock_rabbitmq_post_message: mock.Mock,
    app_settings: ApplicationSettings,
    app: FastAPI,
    **message_update_kwargs,
):
    assert app_settings.AUTOSCALING_NODES_MONITORING
    default_message = RabbitAutoscalingStatusMessage(
        origin=f"{app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS}",
        nodes_total=0,
        nodes_active=0,
        nodes_drained=0,
        cluster_total_resources=Resources.create_as_empty().dict(),
        cluster_used_resources=Resources.create_as_empty().dict(),
        instances_pending=0,
        instances_running=0,
    )
    expected_message = default_message.copy(update=message_update_kwargs)
    mock_rabbitmq_post_message.assert_called_once_with(
        app,
        expected_message,
    )


async def test_cluster_scaling_from_labelled_services_with_no_services_does_nothing(
    minimal_configuration: None,
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    mock_start_aws_instance: mock.Mock,
    mock_terminate_instances: mock.Mock,
    mock_rabbitmq_post_message: mock.Mock,
):
    await auto_scale_cluster(
        app=initialized_app, scale_cluster_cb=scale_cluster_with_labelled_services
    )
    mock_start_aws_instance.assert_not_called()
    mock_terminate_instances.assert_not_called()
    _assert_rabbit_autoscaling_message_sent(
        mock_rabbitmq_post_message, app_settings, initialized_app
    )


async def test_cluster_scaling_from_labelled_services_with_no_services_and_machine_buffer_starts_expected_machines(
    minimal_configuration: None,
    mock_machines_buffer: int,
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    aws_allowed_ec2_instance_type_names: list[str],
    mock_rabbitmq_post_message: mock.Mock,
    mock_compute_node_used_resources: mock.Mock,
    mock_find_node_with_name: mock.Mock,
    mock_tag_node: mock.Mock,
    fake_node: Node,
    ec2_client: EC2Client,
):
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    assert (
        app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER
        == mock_machines_buffer
    )
    await auto_scale_cluster(
        app=initialized_app, scale_cluster_cb=scale_cluster_with_labelled_services
    )
    await _assert_ec2_instances(
        ec2_client,
        num_reservations=1,
        num_instances=mock_machines_buffer,
        instance_type=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES[
            0
        ],
        instance_state="running",
    )
    _assert_rabbit_autoscaling_message_sent(
        mock_rabbitmq_post_message,
        app_settings,
        initialized_app,
        instances_pending=mock_machines_buffer,
    )
    mock_rabbitmq_post_message.reset_mock()
    # calling again should attach the new nodes to the reserve, but nothing should start
    await auto_scale_cluster(
        app=initialized_app, scale_cluster_cb=scale_cluster_with_labelled_services
    )
    await _assert_ec2_instances(
        ec2_client,
        num_reservations=1,
        num_instances=mock_machines_buffer,
        instance_type=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES[
            0
        ],
        instance_state="running",
    )
    assert fake_node.Description
    assert fake_node.Description.Resources
    assert fake_node.Description.Resources.NanoCPUs
    assert fake_node.Description.Resources.MemoryBytes
    _assert_rabbit_autoscaling_message_sent(
        mock_rabbitmq_post_message,
        app_settings,
        initialized_app,
        nodes_total=mock_machines_buffer,
        nodes_drained=mock_machines_buffer,
        instances_running=mock_machines_buffer,
        cluster_total_resources={
            "cpus": mock_machines_buffer
            * fake_node.Description.Resources.NanoCPUs
            / 1e9,
            "ram": mock_machines_buffer * fake_node.Description.Resources.MemoryBytes,
        },
    )

    # calling it again should not create anything new
    for _ in range(10):
        await auto_scale_cluster(
            app=initialized_app, scale_cluster_cb=scale_cluster_with_labelled_services
        )
    await _assert_ec2_instances(
        ec2_client,
        num_reservations=1,
        num_instances=mock_machines_buffer,
        instance_type=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES[
            0
        ],
        instance_state="running",
    )


async def test_cluster_scaling_from_labelled_services_with_service_with_too_much_resources_starts_nothing(
    minimal_configuration: None,
    service_monitored_labels: dict[DockerLabelKey, str],
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    create_service: Callable[
        [dict[str, Any], dict[DockerLabelKey, str], str], Awaitable[Service]
    ],
    task_template: dict[str, Any],
    create_task_reservations: Callable[[int, int], dict[str, Any]],
    mock_start_aws_instance: mock.Mock,
    mock_terminate_instances: mock.Mock,
    mock_rabbitmq_post_message: mock.Mock,
):
    task_template_with_too_many_resource = task_template | create_task_reservations(
        1000, 0
    )
    await create_service(
        task_template_with_too_many_resource,
        service_monitored_labels,
        "pending",
    )

    await auto_scale_cluster(
        app=initialized_app, scale_cluster_cb=scale_cluster_with_labelled_services
    )
    mock_start_aws_instance.assert_not_called()
    mock_terminate_instances.assert_not_called()
    _assert_rabbit_autoscaling_message_sent(
        mock_rabbitmq_post_message, app_settings, initialized_app
    )


async def _assert_ec2_instances(
    ec2_client: EC2Client,
    *,
    num_reservations: int,
    num_instances: int,
    instance_type: str,
    instance_state: str,
):
    all_instances = await ec2_client.describe_instances()

    assert len(all_instances["Reservations"]) == num_reservations
    for reservation in all_instances["Reservations"]:
        assert "Instances" in reservation
        assert len(reservation["Instances"]) == num_instances
        for instance in reservation["Instances"]:
            assert "InstanceType" in instance
            assert instance["InstanceType"] == instance_type
            assert "Tags" in instance
            assert instance["Tags"]
            expected_tag_keys = [
                "io.simcore.autoscaling.version",
                "io.simcore.autoscaling.monitored_nodes_labels",
                "io.simcore.autoscaling.monitored_services_labels",
                "Name",
            ]
            for tag_dict in instance["Tags"]:
                assert "Key" in tag_dict
                assert "Value" in tag_dict

                assert tag_dict["Key"] in expected_tag_keys
            assert "PrivateDnsName" in instance
            instance_private_dns_name = instance["PrivateDnsName"]
            assert instance_private_dns_name.endswith(".ec2.internal")
            assert "State" in instance
            state = instance["State"]
            assert "Name" in state
            assert state["Name"] == instance_state

            assert "InstanceId" in instance
            user_data = await ec2_client.describe_instance_attribute(
                Attribute="userData", InstanceId=instance["InstanceId"]
            )
            assert "UserData" in user_data
            assert "Value" in user_data["UserData"]
            user_data = base64.b64decode(user_data["UserData"]["Value"]).decode()
            assert user_data.count("docker swarm join") == 1


async def test_cluster_scaling_up(
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
    mock_tag_node: mock.Mock,
    fake_node: Node,
    mock_rabbitmq_post_message: mock.Mock,
    mock_find_node_with_name: mock.Mock,
    mock_set_node_availability: mock.Mock,
    # mock_cluster_used_resources: mock.Mock,
    mock_compute_node_used_resources: mock.Mock,
):
    # we have nothing running now
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]

    # create a task that needs more power
    await create_service(
        task_template | create_task_reservations(4, parse_obj_as(ByteSize, "128GiB")),
        service_monitored_labels,
        "pending",
    )

    # this should trigger a scaling up as we have no nodes
    await auto_scale_cluster(
        app=initialized_app, scale_cluster_cb=scale_cluster_with_labelled_services
    )

    # check the instance was started and we have exactly 1
    await _assert_ec2_instances(
        ec2_client,
        num_reservations=1,
        num_instances=1,
        instance_type="r5n.4xlarge",
        instance_state="running",
    )

    # as the new node is already running, but is not yet connected, hence not tagged and drained
    mock_find_node_with_name.assert_not_called()
    mock_tag_node.assert_not_called()
    mock_set_node_availability.assert_not_called()
    mock_compute_node_used_resources.assert_not_called()
    # check rabbit messages were sent
    _assert_rabbit_autoscaling_message_sent(
        mock_rabbitmq_post_message,
        app_settings,
        initialized_app,
        instances_running=0,
        instances_pending=1,
    )
    mock_rabbitmq_post_message.reset_mock()

    # 2. running this again should not scale again, but tag the node and make it available
    await auto_scale_cluster(
        app=initialized_app, scale_cluster_cb=scale_cluster_with_labelled_services
    )
    mock_compute_node_used_resources.assert_called_once_with(
        get_docker_client(initialized_app),
        fake_node,
    )
    # check the number of instances did not change and is still running
    await _assert_ec2_instances(
        ec2_client,
        num_reservations=1,
        num_instances=1,
        instance_type="r5n.4xlarge",
        instance_state="running",
    )
    # the node is tagged and made active right away since we still have the pending task
    mock_find_node_with_name.assert_called_once()
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
        available=False,
    )
    mock_set_node_availability.assert_called_once_with(
        get_docker_client(initialized_app), fake_node, available=True
    )

    # check rabbit messages were sent
    assert fake_node.Description
    assert fake_node.Description.Resources
    assert fake_node.Description.Resources.NanoCPUs
    _assert_rabbit_autoscaling_message_sent(
        mock_rabbitmq_post_message,
        app_settings,
        initialized_app,
        nodes_total=1,
        nodes_active=1,
        cluster_total_resources={
            "cpus": fake_node.Description.Resources.NanoCPUs / 1e9,
            "ram": fake_node.Description.Resources.MemoryBytes,
        },
        cluster_used_resources={
            "cpus": float(0),
            "ram": 0,
        },
        instances_running=1,
    )
    mock_rabbitmq_post_message.reset_mock()


@dataclass(frozen=True)
class _ScaleUpParams:
    service_resources: Resources
    num_services: int
    expected_instance_type: str
    expected_num_instances: int


@pytest.mark.parametrize(
    "scale_up_params",
    [
        pytest.param(
            _ScaleUpParams(
                service_resources=Resources(
                    cpus=5, ram=parse_obj_as(ByteSize, "36Gib")
                ),
                num_services=10,
                expected_instance_type="g3.4xlarge",
                expected_num_instances=4,
            ),
            id="sim4life-light",
        )
    ],
)
async def test_cluster_scaling_up_starts_multiple_instances(
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
    mock_tag_node: mock.Mock,
    fake_node: Node,
    scale_up_params: _ScaleUpParams,
    mock_rabbitmq_post_message: mock.Mock,
    mock_find_node_with_name: mock.Mock,
    mock_set_node_availability: mock.Mock,
):
    # we have nothing running now
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]

    # create several tasks that needs more power
    await asyncio.gather(
        *(
            create_service(
                task_template
                | create_task_reservations(
                    int(scale_up_params.service_resources.cpus),
                    scale_up_params.service_resources.ram,
                ),
                service_monitored_labels,
                "pending",
            )
            for _ in range(scale_up_params.num_services)
        )
    )

    # run the code
    await auto_scale_cluster(
        app=initialized_app, scale_cluster_cb=scale_cluster_with_labelled_services
    )

    # check the instances were started
    await _assert_ec2_instances(
        ec2_client,
        num_reservations=1,
        num_instances=scale_up_params.expected_num_instances,
        instance_type="g3.4xlarge",
        instance_state="running",
    )

    # as the new node is already running, but is not yet connected, hence not tagged and drained
    mock_find_node_with_name.assert_not_called()
    mock_tag_node.assert_not_called()
    mock_set_node_availability.assert_not_called()
    # check rabbit messages were sent
    _assert_rabbit_autoscaling_message_sent(
        mock_rabbitmq_post_message,
        app_settings,
        initialized_app,
        instances_pending=scale_up_params.expected_num_instances,
    )
    mock_rabbitmq_post_message.reset_mock()


async def test__deactivate_empty_nodes(
    minimal_configuration: None,
    initialized_app: FastAPI,
    cluster: Callable[..., Cluster],
    host_node: Node,
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
    mock_set_node_availability: mock.Mock,
):
    # since we have no service running, we expect the passed node to be set to drain
    active_cluster = cluster(
        active_nodes=[AssociatedInstance(host_node, fake_ec2_instance_data())]
    )
    updated_cluster = await _deactivate_empty_nodes(initialized_app, active_cluster)
    assert not updated_cluster.active_nodes
    assert updated_cluster.drained_nodes == active_cluster.active_nodes
    mock_set_node_availability.assert_called_once_with(
        mock.ANY, host_node, available=False
    )


async def test__deactivate_empty_nodes_to_drain_when_services_running_are_missing_labels(
    minimal_configuration: None,
    initialized_app: FastAPI,
    cluster: Callable[..., Cluster],
    host_node: Node,
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
    mock_set_node_availability: mock.Mock,
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
    active_cluster = cluster(
        active_nodes=[AssociatedInstance(host_node, fake_ec2_instance_data())]
    )
    updated_cluster = await _deactivate_empty_nodes(initialized_app, active_cluster)
    assert not updated_cluster.active_nodes
    assert updated_cluster.drained_nodes == active_cluster.active_nodes
    mock_set_node_availability.assert_called_once_with(
        mock.ANY, host_node, available=False
    )


async def test__deactivate_empty_nodes_does_not_drain_if_service_is_running_with_correct_labels(
    minimal_configuration: None,
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    cluster: Callable[..., Cluster],
    host_node: Node,
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
    mock_set_node_availability: mock.Mock,
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
    active_cluster = cluster(
        active_nodes=[AssociatedInstance(host_node, fake_ec2_instance_data())]
    )
    updated_cluster = await _deactivate_empty_nodes(initialized_app, active_cluster)
    assert updated_cluster == active_cluster
    mock_set_node_availability.assert_not_called()


async def test__find_terminateable_nodes_with_no_hosts(
    minimal_configuration: None,
    initialized_app: FastAPI,
    cluster: Callable[..., Cluster],
    host_node: Node,
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
):
    # there is no node to terminate here since nothing is drained
    active_cluster = cluster(
        active_nodes=[AssociatedInstance(host_node, fake_ec2_instance_data())],
        drained_nodes=[],
        reserve_drained_nodes=[AssociatedInstance(host_node, fake_ec2_instance_data())],
    )
    assert await _find_terminateable_instances(initialized_app, active_cluster) == []


async def test__find_terminateable_nodes_with_drained_host(
    minimal_configuration: None,
    with_valid_time_before_termination: datetime.timedelta,
    initialized_app: FastAPI,
    cluster: Callable[..., Cluster],
    drained_host_node: Node,
    app_settings: ApplicationSettings,
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
):
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    assert (
        app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
        > datetime.timedelta(seconds=10)
    ), "this tests relies on the fact that the time before termination is above 10 seconds"

    # if the instance started just about now, then it should not be terminateable
    active_cluster_with_drained_nodes_started_now = cluster(
        drained_nodes=[
            AssociatedInstance(
                drained_host_node,
                fake_ec2_instance_data(
                    launch_time=datetime.datetime.now(datetime.timezone.utc)
                ),
            )
        ],
        reserve_drained_nodes=[
            AssociatedInstance(
                drained_host_node,
                fake_ec2_instance_data(
                    launch_time=datetime.datetime.now(datetime.timezone.utc)
                ),
            )
        ],
    )
    assert (
        await _find_terminateable_instances(
            initialized_app, active_cluster_with_drained_nodes_started_now
        )
        == []
    )

    # if the instance started just after the termination time, even on several days, it is not terminateable
    active_cluster_with_drained_nodes_not_inthe_window = cluster(
        drained_nodes=[
            AssociatedInstance(
                drained_host_node,
                fake_ec2_instance_data(
                    launch_time=datetime.datetime.now(datetime.timezone.utc)
                    - app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
                    - datetime.timedelta(days=21)
                    + datetime.timedelta(seconds=10)
                ),
            )
        ],
        reserve_drained_nodes=[
            AssociatedInstance(
                drained_host_node,
                fake_ec2_instance_data(
                    launch_time=datetime.datetime.now(datetime.timezone.utc)
                    - app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
                    - datetime.timedelta(days=21)
                    + datetime.timedelta(seconds=10)
                ),
            )
        ],
    )
    assert (
        await _find_terminateable_instances(
            initialized_app, active_cluster_with_drained_nodes_not_inthe_window
        )
        == []
    )

    # if the instance started just before the termination time, even on several days, it is terminateable
    active_cluster_with_drained_nodes_long_time_ago_terminateable = cluster(
        drained_nodes=[
            AssociatedInstance(
                drained_host_node,
                fake_ec2_instance_data(
                    launch_time=datetime.datetime.now(datetime.timezone.utc)
                    - app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
                    - datetime.timedelta(days=21)
                    - datetime.timedelta(seconds=10),
                ),
            )
        ],
        reserve_drained_nodes=[
            AssociatedInstance(
                drained_host_node,
                fake_ec2_instance_data(
                    launch_time=datetime.datetime.now(datetime.timezone.utc)
                    - app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
                    - datetime.timedelta(days=21)
                    - datetime.timedelta(seconds=10),
                ),
            )
        ],
    )

    assert (
        await _find_terminateable_instances(
            initialized_app,
            active_cluster_with_drained_nodes_long_time_ago_terminateable,
        )
        == active_cluster_with_drained_nodes_long_time_ago_terminateable.drained_nodes
    )


@pytest.fixture
def create_associated_instance(
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
    app_settings: ApplicationSettings,
    faker: Faker,
) -> Callable[[Node, bool], AssociatedInstance]:
    def _creator(node: Node, terminateable_time: bool) -> AssociatedInstance:
        assert app_settings.AUTOSCALING_EC2_INSTANCES
        assert (
            app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
            > datetime.timedelta(seconds=10)
        ), "this tests relies on the fact that the time before termination is above 10 seconds"
        assert app_settings.AUTOSCALING_EC2_INSTANCES
        seconds_delta = (
            -datetime.timedelta(seconds=10)
            if terminateable_time
            else datetime.timedelta(seconds=10)
        )
        return AssociatedInstance(
            node,
            fake_ec2_instance_data(
                launch_time=datetime.datetime.now(datetime.timezone.utc)
                - app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
                - datetime.timedelta(
                    days=faker.pyint(min_value=0, max_value=100),
                    hours=faker.pyint(min_value=0, max_value=100),
                )
                + seconds_delta
            ),
        )

    return _creator


async def test__try_scale_down_cluster_with_no_nodes(
    minimal_configuration: None,
    with_valid_time_before_termination: datetime.timedelta,
    initialized_app: FastAPI,
    cluster: Callable[..., Cluster],
    mock_remove_nodes: mock.Mock,
    host_node: Node,
    drained_host_node: Node,
    create_associated_instance: Callable[[Node, bool], AssociatedInstance],
):
    active_cluster = cluster(
        active_nodes=[create_associated_instance(host_node, True)],
        drained_nodes=[create_associated_instance(drained_host_node, False)],
        reserve_drained_nodes=[create_associated_instance(drained_host_node, True)],
    )
    updated_cluster = await _try_scale_down_cluster(initialized_app, active_cluster)
    assert updated_cluster == active_cluster
    mock_remove_nodes.assert_not_called()


async def test__try_scale_down_cluster(
    minimal_configuration: None,
    with_valid_time_before_termination: datetime.timedelta,
    initialized_app: FastAPI,
    cluster: Callable[..., Cluster],
    host_node: Node,
    drained_host_node: Node,
    mock_terminate_instances: mock.Mock,
    mock_remove_nodes: mock.Mock,
    app_settings: ApplicationSettings,
    create_associated_instance: Callable[[Node, bool], AssociatedInstance],
):
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    assert (
        app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
        > datetime.timedelta(seconds=10)
    ), "this tests relies on the fact that the time before termination is above 10 seconds"

    active_cluster = cluster(
        active_nodes=[create_associated_instance(host_node, True)],
        drained_nodes=[create_associated_instance(drained_host_node, True)],
        reserve_drained_nodes=[create_associated_instance(drained_host_node, True)],
    )

    updated_cluster = await _try_scale_down_cluster(initialized_app, active_cluster)
    assert not updated_cluster.drained_nodes
    assert updated_cluster.reserve_drained_nodes
    assert updated_cluster.reserve_drained_nodes == active_cluster.reserve_drained_nodes
    assert updated_cluster.active_nodes
    assert updated_cluster.active_nodes == active_cluster.active_nodes
    mock_terminate_instances.assert_called_once()
    mock_remove_nodes.assert_called_once()


async def test__activate_drained_nodes_with_no_tasks(
    minimal_configuration: None,
    with_valid_time_before_termination: datetime.timedelta,
    initialized_app: FastAPI,
    host_node: Node,
    drained_host_node: Node,
    mock_tag_node: mock.Mock,
    cluster: Callable[..., Cluster],
    create_associated_instance: Callable[[Node, bool], AssociatedInstance],
):
    # no tasks, does nothing and returns True
    empty_cluster = cluster()
    still_pending_tasks, updated_cluster = await _activate_drained_nodes(
        initialized_app, empty_cluster, []
    )
    assert not still_pending_tasks
    assert updated_cluster == empty_cluster

    active_cluster = cluster(
        active_nodes=[create_associated_instance(host_node, True)],
        drained_nodes=[create_associated_instance(drained_host_node, True)],
        reserve_drained_nodes=[create_associated_instance(drained_host_node, True)],
    )
    still_pending_tasks, updated_cluster = await _activate_drained_nodes(
        initialized_app,
        active_cluster,
        [],
    )
    assert not still_pending_tasks
    assert updated_cluster == active_cluster
    mock_tag_node.assert_not_called()


async def test__activate_drained_nodes_with_no_drained_nodes(
    minimal_configuration: None,
    with_valid_time_before_termination: datetime.timedelta,
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
    cluster: Callable[..., Cluster],
    create_associated_instance: Callable[[Node, bool], AssociatedInstance],
):
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

    cluster_without_drained_nodes = cluster(
        active_nodes=[create_associated_instance(host_node, True)]
    )
    still_pending_tasks, updated_cluster = await _activate_drained_nodes(
        initialized_app,
        cluster_without_drained_nodes,
        service_tasks,
    )
    assert still_pending_tasks == service_tasks
    assert updated_cluster == cluster_without_drained_nodes
    mock_tag_node.assert_not_called()


async def test__activate_drained_nodes_with_drained_node(
    minimal_configuration: None,
    with_valid_time_before_termination: datetime.timedelta,
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
    cluster: Callable[..., Cluster],
    create_associated_instance: Callable[[Node, bool], AssociatedInstance],
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

    cluster_with_drained_nodes = cluster(
        drained_nodes=[create_associated_instance(drained_host_node, True)]
    )

    still_pending_tasks, updated_cluster = await _activate_drained_nodes(
        initialized_app,
        cluster_with_drained_nodes,
        service_tasks,
    )
    assert not still_pending_tasks
    assert updated_cluster.active_nodes == cluster_with_drained_nodes.drained_nodes
    assert drained_host_node.Spec
    mock_tag_node.assert_called_once_with(
        mock.ANY, drained_host_node, tags=drained_host_node.Spec.Labels, available=True
    )
