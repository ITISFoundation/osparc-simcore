# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements

import asyncio
import base64
import datetime
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from unittest import mock

import aiodocker
import arrow
import pytest
from aws_library.ec2.models import EC2InstanceData, Resources
from fastapi import FastAPI
from models_library.docker import (
    DOCKER_TASK_EC2_INSTANCE_TYPE_PLACEMENT_CONSTRAINT_KEY,
    DockerLabelKey,
    StandardSimcoreDockerLabels,
)
from models_library.generated_models.docker_rest_api import (
    Availability,
    Node,
    NodeState,
    NodeStatus,
    Service,
    Task,
)
from models_library.rabbitmq_messages import RabbitAutoscalingStatusMessage
from pydantic import ByteSize, parse_obj_as
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.utils_envs import EnvVarsDict
from simcore_service_autoscaling.core.settings import ApplicationSettings
from simcore_service_autoscaling.models import AssociatedInstance, Cluster
from simcore_service_autoscaling.modules.auto_scaling_core import (
    _activate_drained_nodes,
    _deactivate_empty_nodes,
    _find_terminateable_instances,
    _try_scale_down_cluster,
    auto_scale_cluster,
)
from simcore_service_autoscaling.modules.auto_scaling_mode_dynamic import (
    DynamicAutoscaling,
)
from simcore_service_autoscaling.modules.docker import (
    AutoscalingDocker,
    get_docker_client,
)
from simcore_service_autoscaling.utils.utils_docker import (
    _OSPARC_SERVICE_READY_LABEL_KEY,
    _OSPARC_SERVICES_READY_DATETIME_LABEL_KEY,
)
from types_aiobotocore_ec2.client import EC2Client
from types_aiobotocore_ec2.literals import InstanceTypeType


@pytest.fixture
def mock_terminate_instances(mocker: MockerFixture) -> Iterator[mock.Mock]:
    return mocker.patch(
        "simcore_service_autoscaling.modules.ec2.SimcoreEC2API.terminate_instances",
        autospec=True,
    )


@pytest.fixture
def mock_start_aws_instance(
    mocker: MockerFixture,
    aws_instance_private_dns: str,
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
) -> Iterator[mock.Mock]:
    return mocker.patch(
        "simcore_service_autoscaling.modules.ec2.SimcoreEC2API.start_aws_instance",
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
        "simcore_service_autoscaling.modules.auto_scaling_core.utils_docker.find_node_with_name",
        autospec=True,
        return_value=fake_node,
    )


@pytest.fixture
def mock_remove_nodes(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "simcore_service_autoscaling.modules.auto_scaling_core.utils_docker.remove_nodes",
        autospec=True,
    )


@pytest.fixture
def mock_compute_node_used_resources(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "simcore_service_autoscaling.modules.auto_scaling_core.utils_docker.compute_node_used_resources",
        autospec=True,
        return_value=Resources.create_as_empty(),
    )


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
    with_labelize_drain_nodes: EnvVarsDict,
    docker_swarm: None,
    mocked_ec2_server_envs: EnvVarsDict,
    enabled_dynamic_mode: EnvVarsDict,
    mocked_ec2_instances_envs: EnvVarsDict,
    disabled_rabbitmq: None,
    disable_dynamic_service_background_task: None,
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
        origin=f"dynamic:node_labels={app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS}",
        nodes_total=0,
        nodes_active=0,
        nodes_drained=0,
        cluster_total_resources=Resources.create_as_empty().dict(),
        cluster_used_resources=Resources.create_as_empty().dict(),
        instances_pending=0,
        instances_running=0,
    )
    expected_message = default_message.copy(update=message_update_kwargs)
    assert mock_rabbitmq_post_message.call_args == mock.call(app, expected_message)


async def test_cluster_scaling_from_labelled_services_with_no_services_does_nothing(
    minimal_configuration: None,
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    mock_start_aws_instance: mock.Mock,
    mock_terminate_instances: mock.Mock,
    mock_rabbitmq_post_message: mock.Mock,
):
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )
    mock_start_aws_instance.assert_not_called()
    mock_terminate_instances.assert_not_called()
    _assert_rabbit_autoscaling_message_sent(
        mock_rabbitmq_post_message, app_settings, initialized_app
    )


async def test_cluster_scaling_from_labelled_services_with_no_services_and_machine_buffer_starts_expected_machines(
    patch_ec2_client_start_aws_instances_min_number_of_instances: mock.Mock,
    minimal_configuration: None,
    mock_machines_buffer: int,
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    aws_allowed_ec2_instance_type_names_env: list[str],
    mock_rabbitmq_post_message: mock.Mock,
    mock_compute_node_used_resources: mock.Mock,
    mock_find_node_with_name: mock.Mock,
    mock_docker_tag_node: mock.Mock,
    fake_node: Node,
    ec2_client: EC2Client,
):
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    assert (
        mock_machines_buffer
        == app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER
    )
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )
    await _assert_ec2_instances(
        ec2_client,
        num_reservations=1,
        num_instances=mock_machines_buffer,
        instance_type=next(
            iter(app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES)
        ),
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
        app=initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )
    await _assert_ec2_instances(
        ec2_client,
        num_reservations=1,
        num_instances=mock_machines_buffer,
        instance_type=next(
            iter(app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES)
        ),
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
            app=initialized_app, auto_scaling_mode=DynamicAutoscaling()
        )
    await _assert_ec2_instances(
        ec2_client,
        num_reservations=1,
        num_instances=mock_machines_buffer,
        instance_type=next(
            iter(app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES)
        ),
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
        app=initialized_app, auto_scaling_mode=DynamicAutoscaling()
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
) -> list[str]:
    all_instances = await ec2_client.describe_instances()
    internal_dns_names = []
    assert len(all_instances["Reservations"]) == num_reservations
    for reservation in all_instances["Reservations"]:
        assert "Instances" in reservation
        assert (
            len(reservation["Instances"]) == num_instances
        ), f"expected {num_instances}, found {len(reservation['Instances'])}"
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
                "user_id",
                "wallet_id",
                "osparc-tag",
            ]
            for tag_dict in instance["Tags"]:
                assert "Key" in tag_dict
                assert "Value" in tag_dict

                assert tag_dict["Key"] in expected_tag_keys
            assert "PrivateDnsName" in instance
            instance_private_dns_name = instance["PrivateDnsName"]
            assert instance_private_dns_name.endswith(".ec2.internal")
            internal_dns_names.append(instance_private_dns_name)
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
    return internal_dns_names


@pytest.mark.acceptance_test()
@pytest.mark.parametrize(
    "docker_service_imposed_ec2_type, docker_service_ram, expected_ec2_type",
    [
        pytest.param(
            None,
            parse_obj_as(ByteSize, "128Gib"),
            "r5n.4xlarge",
            id="No explicit instance defined",
        ),
        pytest.param(
            "t2.xlarge",
            parse_obj_as(ByteSize, "4Gib"),
            "t2.xlarge",
            id="Explicitely ask for t2.xlarge",
        ),
        pytest.param(
            "r5n.8xlarge",
            parse_obj_as(ByteSize, "128Gib"),
            "r5n.8xlarge",
            id="Explicitely ask for r5n.8xlarge",
        ),
    ],
)
async def test_cluster_scaling_up_and_down(  # noqa: PLR0915
    minimal_configuration: None,
    service_monitored_labels: dict[DockerLabelKey, str],
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    create_service: Callable[
        [dict[str, Any], dict[DockerLabelKey, str], str, list[str]], Awaitable[Service]
    ],
    task_template: dict[str, Any],
    create_task_reservations: Callable[[int, int], dict[str, Any]],
    ec2_client: EC2Client,
    mock_docker_tag_node: mock.Mock,
    fake_node: Node,
    mock_rabbitmq_post_message: mock.Mock,
    mock_find_node_with_name: mock.Mock,
    mock_docker_set_node_availability: mock.Mock,
    mock_compute_node_used_resources: mock.Mock,
    mocker: MockerFixture,
    docker_service_imposed_ec2_type: InstanceTypeType | None,
    docker_service_ram: ByteSize,
    expected_ec2_type: InstanceTypeType,
    async_docker_client: aiodocker.Docker,
    with_drain_nodes_labelled: bool,
):
    # we have nothing running now
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]

    # create a task that needs more power
    docker_service = await create_service(
        task_template | create_task_reservations(4, docker_service_ram),
        service_monitored_labels,
        "pending",
        (
            [
                f"node.labels.{DOCKER_TASK_EC2_INSTANCE_TYPE_PLACEMENT_CONSTRAINT_KEY}=={ docker_service_imposed_ec2_type}"
            ]
            if docker_service_imposed_ec2_type
            else []
        ),
    )

    # this should trigger a scaling up as we have no nodes
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )

    # check the instance was started and we have exactly 1
    await _assert_ec2_instances(
        ec2_client,
        num_reservations=1,
        num_instances=1,
        instance_type=expected_ec2_type,
        instance_state="running",
    )

    # as the new node is already running, but is not yet connected, hence not tagged and drained
    mock_find_node_with_name.assert_not_called()
    mock_docker_tag_node.assert_not_called()
    mock_docker_set_node_availability.assert_not_called()
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
        app=initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )

    fake_attached_node = deepcopy(fake_node)
    assert fake_attached_node.Spec
    fake_attached_node.Spec.Availability = (
        Availability.active if with_drain_nodes_labelled else Availability.drain
    )
    assert fake_attached_node.Spec.Labels
    assert app_settings.AUTOSCALING_NODES_MONITORING
    expected_docker_node_tags = {
        tag_key: "true"
        for tag_key in (
            app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS
            + app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NEW_NODES_LABELS
        )
    } | {DOCKER_TASK_EC2_INSTANCE_TYPE_PLACEMENT_CONSTRAINT_KEY: expected_ec2_type}
    fake_attached_node.Spec.Labels |= expected_docker_node_tags | {
        _OSPARC_SERVICE_READY_LABEL_KEY: "false"
    }

    # the node is tagged and made active right away since we still have the pending task
    mock_find_node_with_name.assert_called_once()
    mock_find_node_with_name.reset_mock()

    assert mock_docker_tag_node.call_count == 2
    assert fake_node.Spec
    assert fake_node.Spec.Labels
    # check attach call
    assert mock_docker_tag_node.call_args_list[0] == mock.call(
        get_docker_client(initialized_app),
        fake_node,
        tags=fake_node.Spec.Labels
        | expected_docker_node_tags
        | {
            _OSPARC_SERVICE_READY_LABEL_KEY: "false",
            _OSPARC_SERVICES_READY_DATETIME_LABEL_KEY: mock.ANY,
        },
        available=with_drain_nodes_labelled,
    )
    # update our fake node
    fake_attached_node.Spec.Labels[
        _OSPARC_SERVICES_READY_DATETIME_LABEL_KEY
    ] = mock_docker_tag_node.call_args_list[0][1]["tags"][
        _OSPARC_SERVICES_READY_DATETIME_LABEL_KEY
    ]
    # check the activate time is later than attach time
    assert arrow.get(
        mock_docker_tag_node.call_args_list[1][1]["tags"][
            _OSPARC_SERVICES_READY_DATETIME_LABEL_KEY
        ]
    ) > arrow.get(
        mock_docker_tag_node.call_args_list[0][1]["tags"][
            _OSPARC_SERVICES_READY_DATETIME_LABEL_KEY
        ]
    )
    mock_compute_node_used_resources.assert_called_once_with(
        get_docker_client(initialized_app),
        fake_attached_node,
    )
    mock_compute_node_used_resources.reset_mock()
    # check activate call
    assert mock_docker_tag_node.call_args_list[1] == mock.call(
        get_docker_client(initialized_app),
        fake_attached_node,
        tags=fake_node.Spec.Labels
        | expected_docker_node_tags
        | {
            _OSPARC_SERVICE_READY_LABEL_KEY: "true",
            _OSPARC_SERVICES_READY_DATETIME_LABEL_KEY: mock.ANY,
        },
        available=True,
    )
    # update our fake node
    fake_attached_node.Spec.Labels[
        _OSPARC_SERVICES_READY_DATETIME_LABEL_KEY
    ] = mock_docker_tag_node.call_args_list[1][1]["tags"][
        _OSPARC_SERVICES_READY_DATETIME_LABEL_KEY
    ]
    mock_docker_tag_node.reset_mock()
    mock_docker_set_node_availability.assert_not_called()

    # check the number of instances did not change and is still running
    internal_dns_names = await _assert_ec2_instances(
        ec2_client,
        num_reservations=1,
        num_instances=1,
        instance_type=expected_ec2_type,
        instance_state="running",
    )
    assert len(internal_dns_names) == 1
    internal_dns_name = internal_dns_names[0].removesuffix(".ec2.internal")

    # check rabbit messages were sent, we do have worker
    assert fake_attached_node.Description
    assert fake_attached_node.Description.Resources
    assert fake_attached_node.Description.Resources.NanoCPUs
    _assert_rabbit_autoscaling_message_sent(
        mock_rabbitmq_post_message,
        app_settings,
        initialized_app,
        nodes_total=1,
        nodes_active=1,
        cluster_total_resources={
            "cpus": fake_attached_node.Description.Resources.NanoCPUs / 1e9,
            "ram": fake_attached_node.Description.Resources.MemoryBytes,
        },
        cluster_used_resources={
            "cpus": float(0),
            "ram": 0,
        },
        instances_running=1,
    )
    mock_rabbitmq_post_message.reset_mock()

    # now we have 1 monitored node that needs to be mocked
    fake_attached_node.Spec.Labels[_OSPARC_SERVICE_READY_LABEL_KEY] = "true"
    fake_attached_node.Status = NodeStatus(
        State=NodeState.ready, Message=None, Addr=None
    )
    fake_attached_node.Spec.Availability = Availability.active
    fake_attached_node.Description.Hostname = internal_dns_name

    auto_scaling_mode = DynamicAutoscaling()
    mocker.patch.object(
        auto_scaling_mode,
        "get_monitored_nodes",
        autospec=True,
        return_value=[fake_attached_node],
    )

    # 3. calling this multiple times should do nothing
    num_useless_calls = 10
    for _ in range(num_useless_calls):
        await auto_scale_cluster(
            app=initialized_app, auto_scaling_mode=auto_scaling_mode
        )
    mock_compute_node_used_resources.assert_called()
    assert mock_compute_node_used_resources.call_count == num_useless_calls * 2
    mock_compute_node_used_resources.reset_mock()
    mock_find_node_with_name.assert_not_called()
    mock_docker_tag_node.assert_not_called()
    mock_docker_set_node_availability.assert_not_called()
    # check the number of instances did not change and is still running
    await _assert_ec2_instances(
        ec2_client,
        num_reservations=1,
        num_instances=1,
        instance_type=expected_ec2_type,
        instance_state="running",
    )

    # check rabbit messages were sent
    mock_rabbitmq_post_message.assert_called()
    assert mock_rabbitmq_post_message.call_count == num_useless_calls
    mock_rabbitmq_post_message.reset_mock()

    #
    # 4. now scaling down by removing the docker service
    #
    assert docker_service.ID
    await async_docker_client.services.delete(docker_service.ID)
    #
    await auto_scale_cluster(app=initialized_app, auto_scaling_mode=auto_scaling_mode)
    # check the number of instances did not change and is still running
    await _assert_ec2_instances(
        ec2_client,
        num_reservations=1,
        num_instances=1,
        instance_type=expected_ec2_type,
        instance_state="running",
    )
    mock_docker_set_node_availability.assert_not_called()
    mock_docker_tag_node.assert_called_once_with(
        get_docker_client(initialized_app),
        fake_attached_node,
        tags=fake_attached_node.Spec.Labels
        | {
            _OSPARC_SERVICE_READY_LABEL_KEY: "false",
            _OSPARC_SERVICES_READY_DATETIME_LABEL_KEY: mock.ANY,
        },
        available=with_drain_nodes_labelled,
    )
    # check the datetime was updated
    assert arrow.get(
        mock_docker_tag_node.call_args_list[0][1]["tags"][
            _OSPARC_SERVICES_READY_DATETIME_LABEL_KEY
        ]
    ) > arrow.get(
        fake_attached_node.Spec.Labels[_OSPARC_SERVICES_READY_DATETIME_LABEL_KEY]
    )
    mock_docker_tag_node.reset_mock()

    # calling again does the exact same
    await auto_scale_cluster(app=initialized_app, auto_scaling_mode=auto_scaling_mode)
    mock_docker_set_node_availability.assert_not_called()
    mock_docker_tag_node.assert_called_once_with(
        get_docker_client(initialized_app),
        fake_attached_node,
        tags=fake_attached_node.Spec.Labels
        | {
            _OSPARC_SERVICE_READY_LABEL_KEY: "false",
            _OSPARC_SERVICES_READY_DATETIME_LABEL_KEY: mock.ANY,
        },
        available=with_drain_nodes_labelled,
    )
    mock_docker_tag_node.reset_mock()

    await _assert_ec2_instances(
        ec2_client,
        num_reservations=1,
        num_instances=1,
        instance_type=expected_ec2_type,
        instance_state="running",
    )

    # we artifically set the node to drain
    fake_attached_node.Spec.Availability = Availability.drain
    fake_attached_node.Spec.Labels[_OSPARC_SERVICE_READY_LABEL_KEY] = "false"
    fake_attached_node.Spec.Labels[
        _OSPARC_SERVICES_READY_DATETIME_LABEL_KEY
    ] = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()

    # the node will be not be terminated before the timeout triggers
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    assert (
        datetime.timedelta(seconds=5)
        < app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
    )
    mocked_docker_remove_node = mocker.patch(
        "simcore_service_autoscaling.modules.auto_scaling_core.utils_docker.remove_nodes",
        return_value=None,
        autospec=True,
    )
    await auto_scale_cluster(app=initialized_app, auto_scaling_mode=auto_scaling_mode)
    mocked_docker_remove_node.assert_not_called()
    await _assert_ec2_instances(
        ec2_client,
        num_reservations=1,
        num_instances=1,
        instance_type=expected_ec2_type,
        instance_state="running",
    )

    # now changing the last update timepoint will trigger the node removal and shutdown the ec2 instance
    fake_attached_node.Spec.Labels[_OSPARC_SERVICES_READY_DATETIME_LABEL_KEY] = (
        datetime.datetime.now(tz=datetime.timezone.utc)
        - app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
        - datetime.timedelta(seconds=1)
    ).isoformat()
    await auto_scale_cluster(app=initialized_app, auto_scaling_mode=auto_scaling_mode)
    mocked_docker_remove_node.assert_called_once_with(
        mock.ANY, nodes=[fake_attached_node], force=True
    )
    await _assert_ec2_instances(
        ec2_client,
        num_reservations=1,
        num_instances=1,
        instance_type=expected_ec2_type,
        instance_state="terminated",
    )


@dataclass(frozen=True)
class _ScaleUpParams:
    imposed_instance_type: str | None
    service_resources: Resources
    num_services: int
    expected_instance_type: str
    expected_num_instances: int


@pytest.mark.parametrize(
    "scale_up_params",
    [
        pytest.param(
            _ScaleUpParams(
                imposed_instance_type=None,
                service_resources=Resources(
                    cpus=5, ram=parse_obj_as(ByteSize, "36Gib")
                ),
                num_services=10,
                expected_instance_type="g3.4xlarge",  # 1 GPU, 16 CPUs, 122GiB
                expected_num_instances=4,
            ),
            id="sim4life-light",
        ),
        pytest.param(
            _ScaleUpParams(
                imposed_instance_type="g4dn.8xlarge",
                service_resources=Resources(
                    cpus=5, ram=parse_obj_as(ByteSize, "20480MB")
                ),
                num_services=7,
                expected_instance_type="g4dn.8xlarge",  # 1 GPU, 32 CPUs, 128GiB
                expected_num_instances=2,
            ),
            id="sim4life",
        ),
    ],
)
async def test_cluster_scaling_up_starts_multiple_instances(
    patch_ec2_client_start_aws_instances_min_number_of_instances: mock.Mock,
    minimal_configuration: None,
    service_monitored_labels: dict[DockerLabelKey, str],
    osparc_docker_label_keys: StandardSimcoreDockerLabels,
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    create_service: Callable[
        [dict[str, Any], dict[DockerLabelKey, str], str, list[str]], Awaitable[Service]
    ],
    task_template: dict[str, Any],
    create_task_reservations: Callable[[int, int], dict[str, Any]],
    ec2_client: EC2Client,
    mock_docker_tag_node: mock.Mock,
    scale_up_params: _ScaleUpParams,
    mock_rabbitmq_post_message: mock.Mock,
    mock_find_node_with_name: mock.Mock,
    mock_docker_set_node_availability: mock.Mock,
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
                service_monitored_labels
                | osparc_docker_label_keys.to_simcore_runtime_docker_labels(),
                "pending",
                (
                    [
                        f"node.labels.{DOCKER_TASK_EC2_INSTANCE_TYPE_PLACEMENT_CONSTRAINT_KEY}=={scale_up_params.imposed_instance_type}"
                    ]
                    if scale_up_params.imposed_instance_type
                    else []
                ),
            )
            for _ in range(scale_up_params.num_services)
        )
    )

    # run the code
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )

    # check the instances were started
    await _assert_ec2_instances(
        ec2_client,
        num_reservations=1,
        num_instances=scale_up_params.expected_num_instances,
        instance_type=scale_up_params.expected_instance_type,
        instance_state="running",
    )

    # as the new node is already running, but is not yet connected, hence not tagged and drained
    mock_find_node_with_name.assert_not_called()
    mock_docker_tag_node.assert_not_called()
    mock_docker_set_node_availability.assert_not_called()
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
    mock_docker_set_node_availability: mock.Mock,
    mock_docker_tag_node: mock.Mock,
    with_drain_nodes_labelled: bool,
):
    # since we have no service running, we expect the passed node to be set to drain
    active_cluster = cluster(
        active_nodes=[
            AssociatedInstance(node=host_node, ec2_instance=fake_ec2_instance_data())
        ]
    )
    updated_cluster = await _deactivate_empty_nodes(initialized_app, active_cluster)
    assert not updated_cluster.active_nodes
    assert len(updated_cluster.drained_nodes) == len(active_cluster.active_nodes)
    mock_docker_set_node_availability.assert_not_called()
    assert host_node.Spec
    assert host_node.Spec.Labels
    mock_docker_tag_node.assert_called_once_with(
        mock.ANY,
        host_node,
        tags=host_node.Spec.Labels
        | {
            _OSPARC_SERVICE_READY_LABEL_KEY: "false",
            _OSPARC_SERVICES_READY_DATETIME_LABEL_KEY: mock.ANY,
        },
        available=with_drain_nodes_labelled,
    )


async def test__deactivate_empty_nodes_to_drain_when_services_running_are_missing_labels(
    minimal_configuration: None,
    initialized_app: FastAPI,
    cluster: Callable[..., Cluster],
    host_node: Node,
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
    mock_docker_set_node_availability: mock.Mock,
    mock_docker_tag_node: mock.Mock,
    create_service: Callable[
        [dict[str, Any], dict[DockerLabelKey, str], str], Awaitable[Service]
    ],
    task_template: dict[str, Any],
    create_task_reservations: Callable[[int, int], dict[str, Any]],
    host_cpu_count: int,
    with_drain_nodes_labelled: bool,
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
        active_nodes=[
            AssociatedInstance(node=host_node, ec2_instance=fake_ec2_instance_data())
        ]
    )
    updated_cluster = await _deactivate_empty_nodes(initialized_app, active_cluster)
    assert not updated_cluster.active_nodes
    assert len(updated_cluster.drained_nodes) == len(active_cluster.active_nodes)
    mock_docker_set_node_availability.assert_not_called()
    assert host_node.Spec
    assert host_node.Spec.Labels
    mock_docker_tag_node.assert_called_once_with(
        mock.ANY,
        host_node,
        tags=host_node.Spec.Labels
        | {
            _OSPARC_SERVICE_READY_LABEL_KEY: "false",
            _OSPARC_SERVICES_READY_DATETIME_LABEL_KEY: mock.ANY,
        },
        available=with_drain_nodes_labelled,
    )


async def test__deactivate_empty_nodes_does_not_drain_if_service_is_running_with_correct_labels(
    minimal_configuration: None,
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    cluster: Callable[..., Cluster],
    host_node: Node,
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
    mock_docker_set_node_availability: mock.Mock,
    mock_docker_tag_node: mock.Mock,
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
    assert host_node.Description
    assert host_node.Description.Resources
    assert host_node.Description.Resources.NanoCPUs
    host_node_resources = Resources.parse_obj(
        {
            "ram": host_node.Description.Resources.MemoryBytes,
            "cpus": host_node.Description.Resources.NanoCPUs / 10**9,
        }
    )
    fake_ec2_instance = fake_ec2_instance_data(resources=host_node_resources)
    fake_associated_instance = AssociatedInstance(
        node=host_node, ec2_instance=fake_ec2_instance
    )
    node_used_resources = await DynamicAutoscaling().compute_node_used_resources(
        initialized_app, fake_associated_instance
    )
    assert node_used_resources

    active_cluster = cluster(
        active_nodes=[
            AssociatedInstance(
                node=host_node,
                ec2_instance=fake_ec2_instance,
                available_resources=host_node_resources - node_used_resources,
            )
        ]
    )
    updated_cluster = await _deactivate_empty_nodes(initialized_app, active_cluster)
    assert updated_cluster == active_cluster
    mock_docker_set_node_availability.assert_not_called()
    mock_docker_tag_node.assert_not_called()


async def test__find_terminateable_nodes_with_no_hosts(
    minimal_configuration: None,
    initialized_app: FastAPI,
    cluster: Callable[..., Cluster],
    host_node: Node,
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
):
    # there is no node to terminate here since nothing is drained
    active_cluster = cluster(
        active_nodes=[
            AssociatedInstance(node=host_node, ec2_instance=fake_ec2_instance_data())
        ],
        drained_nodes=[],
        reserve_drained_nodes=[
            AssociatedInstance(node=host_node, ec2_instance=fake_ec2_instance_data())
        ],
    )
    assert await _find_terminateable_instances(initialized_app, active_cluster) == []


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
        active_nodes=[create_associated_instance(host_node, True)],  # noqa: FBT003
        drained_nodes=[
            create_associated_instance(drained_host_node, False)  # noqa: FBT003
        ],
        reserve_drained_nodes=[
            create_associated_instance(drained_host_node, True)  # noqa: FBT003
        ],
    )
    updated_cluster = await _try_scale_down_cluster(initialized_app, active_cluster)
    assert updated_cluster == active_cluster
    mock_remove_nodes.assert_not_called()


async def test__activate_drained_nodes_with_no_tasks(
    minimal_configuration: None,
    with_valid_time_before_termination: datetime.timedelta,
    initialized_app: FastAPI,
    host_node: Node,
    drained_host_node: Node,
    mock_docker_tag_node: mock.Mock,
    cluster: Callable[..., Cluster],
    create_associated_instance: Callable[[Node, bool], AssociatedInstance],
):
    # no tasks, does nothing and returns True
    empty_cluster = cluster()
    updated_cluster = await _activate_drained_nodes(
        initialized_app, empty_cluster, DynamicAutoscaling()
    )
    assert updated_cluster == empty_cluster

    active_cluster = cluster(
        active_nodes=[create_associated_instance(host_node, True)],  # noqa: FBT003
        drained_nodes=[
            create_associated_instance(drained_host_node, True)  # noqa: FBT003
        ],
        reserve_drained_nodes=[
            create_associated_instance(drained_host_node, True)  # noqa: FBT003
        ],
    )
    updated_cluster = await _activate_drained_nodes(
        initialized_app, active_cluster, DynamicAutoscaling()
    )
    assert updated_cluster == active_cluster
    mock_docker_tag_node.assert_not_called()


async def test__activate_drained_nodes_with_no_drained_nodes(
    minimal_configuration: None,
    with_valid_time_before_termination: datetime.timedelta,
    autoscaling_docker: AutoscalingDocker,
    initialized_app: FastAPI,
    host_node: Node,
    mock_docker_tag_node: mock.Mock,
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
        active_nodes=[create_associated_instance(host_node, True)]  # noqa: FBT003
    )
    updated_cluster = await _activate_drained_nodes(
        initialized_app, cluster_without_drained_nodes, DynamicAutoscaling()
    )
    assert updated_cluster == cluster_without_drained_nodes
    mock_docker_tag_node.assert_not_called()


async def test__activate_drained_nodes_with_drained_node(
    minimal_configuration: None,
    with_valid_time_before_termination: datetime.timedelta,
    autoscaling_docker: AutoscalingDocker,
    initialized_app: FastAPI,
    drained_host_node: Node,
    mock_docker_tag_node: mock.Mock,
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
        drained_nodes=[
            create_associated_instance(drained_host_node, True)  # noqa: FBT003
        ]
    )
    cluster_with_drained_nodes.drained_nodes[0].assign_task(
        service_tasks[0], Resources(cpus=int(host_cpu_count / 2 + 1), ram=ByteSize(0))
    )

    updated_cluster = await _activate_drained_nodes(
        initialized_app, cluster_with_drained_nodes, DynamicAutoscaling()
    )
    assert updated_cluster.active_nodes == cluster_with_drained_nodes.drained_nodes
    assert drained_host_node.Spec
    mock_docker_tag_node.assert_called_once_with(
        mock.ANY,
        drained_host_node,
        tags={
            _OSPARC_SERVICE_READY_LABEL_KEY: "true",
            _OSPARC_SERVICES_READY_DATETIME_LABEL_KEY: mock.ANY,
        },
        available=True,
    )
