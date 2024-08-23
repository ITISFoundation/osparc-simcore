# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements

import asyncio
import datetime
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, cast
from unittest import mock

import aiodocker
import arrow
import pytest
import tenacity
from aws_library.ec2 import EC2InstanceBootSpecific, EC2InstanceData, Resources
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
from pytest_mock import MockType
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.aws_ec2 import assert_autoscaled_dynamic_ec2_instances
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from simcore_service_autoscaling.core.settings import ApplicationSettings
from simcore_service_autoscaling.models import AssociatedInstance, Cluster
from simcore_service_autoscaling.modules import auto_scaling_core
from simcore_service_autoscaling.modules.auto_scaling_core import (
    _activate_drained_nodes,
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
    _OSPARC_NODE_EMPTY_DATETIME_LABEL_KEY,
    _OSPARC_NODE_TERMINATION_PROCESS_LABEL_KEY,
    _OSPARC_SERVICE_READY_LABEL_KEY,
    _OSPARC_SERVICES_READY_DATETIME_LABEL_KEY,
)
from types_aiobotocore_ec2.client import EC2Client
from types_aiobotocore_ec2.literals import InstanceTypeType
from types_aiobotocore_ec2.type_defs import FilterTypeDef, InstanceTypeDef


@pytest.fixture
def mock_terminate_instances(mocker: MockerFixture) -> Iterator[mock.Mock]:
    return mocker.patch(
        "simcore_service_autoscaling.modules.ec2.SimcoreEC2API.terminate_instances",
        autospec=True,
    )


@pytest.fixture
def mock_launch_instances(
    mocker: MockerFixture,
    aws_instance_private_dns: str,
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
) -> Iterator[mock.Mock]:
    return mocker.patch(
        "simcore_service_autoscaling.modules.ec2.SimcoreEC2API.launch_instances",
        autospec=True,
        return_value=fake_ec2_instance_data(aws_private_dns=aws_instance_private_dns),
    )


@pytest.fixture
def mock_rabbitmq_post_message(mocker: MockerFixture) -> Iterator[mock.Mock]:
    return mocker.patch(
        "simcore_service_autoscaling.utils.rabbitmq.post_message", autospec=True
    )


@pytest.fixture
def mock_find_node_with_name_returns_fake_node(
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
    mocked_ssm_server_envs: EnvVarsDict,
    enabled_dynamic_mode: EnvVarsDict,
    mocked_ec2_instances_envs: EnvVarsDict,
    disabled_rabbitmq: None,
    disable_dynamic_service_background_task: None,
    disable_buffers_pool_background_task: None,
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


async def test_cluster_scaling_with_no_services_does_nothing(
    minimal_configuration: None,
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    mock_launch_instances: mock.Mock,
    mock_terminate_instances: mock.Mock,
    mock_rabbitmq_post_message: mock.Mock,
):
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )
    mock_launch_instances.assert_not_called()
    mock_terminate_instances.assert_not_called()
    _assert_rabbit_autoscaling_message_sent(
        mock_rabbitmq_post_message, app_settings, initialized_app
    )


@pytest.fixture
def instance_type_filters(
    ec2_instance_custom_tags: dict[str, str],
) -> Sequence[FilterTypeDef]:
    return [
        *[
            FilterTypeDef(
                Name="tag-key",
                Values=[tag_key],
            )
            for tag_key in ec2_instance_custom_tags
        ],
        FilterTypeDef(
            Name="instance-state-name",
            Values=["pending", "running"],
        ),
    ]


@pytest.fixture
async def spied_cluster_analysis(mocker: MockerFixture) -> MockType:
    return mocker.spy(auto_scaling_core, "_analyze_current_cluster")


async def test_cluster_scaling_with_no_services_and_machine_buffer_starts_expected_machines(
    patch_ec2_client_launch_instancess_min_number_of_instances: mock.Mock,
    minimal_configuration: None,
    mock_machines_buffer: int,
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    aws_allowed_ec2_instance_type_names_env: list[str],
    mock_rabbitmq_post_message: mock.Mock,
    mock_compute_node_used_resources: mock.Mock,
    mock_find_node_with_name_returns_fake_node: mock.Mock,
    mock_docker_tag_node: mock.Mock,
    fake_node: Node,
    ec2_client: EC2Client,
    ec2_instance_custom_tags: dict[str, str],
    instance_type_filters: Sequence[FilterTypeDef],
):
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    assert (
        mock_machines_buffer
        == app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER
    )
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )
    await assert_autoscaled_dynamic_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=mock_machines_buffer,
        expected_instance_type=cast(
            InstanceTypeType,
            next(
                iter(app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES)
            ),
        ),
        expected_instance_state="running",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
        instance_filters=instance_type_filters,
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
    await assert_autoscaled_dynamic_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=mock_machines_buffer,
        expected_instance_type=cast(
            InstanceTypeType,
            next(
                iter(app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES)
            ),
        ),
        expected_instance_state="running",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
        instance_filters=instance_type_filters,
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
    await assert_autoscaled_dynamic_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=mock_machines_buffer,
        expected_instance_type=cast(
            InstanceTypeType,
            next(
                iter(app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES)
            ),
        ),
        expected_instance_state="running",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
        instance_filters=instance_type_filters,
    )


async def test_cluster_scaling_with_service_asking_for_too_much_resources_starts_nothing(
    minimal_configuration: None,
    service_monitored_labels: dict[DockerLabelKey, str],
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    create_service: Callable[
        [dict[str, Any], dict[DockerLabelKey, str], str], Awaitable[Service]
    ],
    task_template: dict[str, Any],
    create_task_reservations: Callable[[int, int], dict[str, Any]],
    mock_launch_instances: mock.Mock,
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
    mock_launch_instances.assert_not_called()
    mock_terminate_instances.assert_not_called()
    _assert_rabbit_autoscaling_message_sent(
        mock_rabbitmq_post_message, app_settings, initialized_app
    )


@dataclass(frozen=True)
class _ScaleUpParams:
    imposed_instance_type: str | None
    service_resources: Resources
    num_services: int
    expected_instance_type: InstanceTypeType
    expected_num_instances: int


def _assert_cluster_state(
    spied_cluster_analysis: MockType, *, expected_calls: int, expected_num_machines: int
) -> None:
    assert spied_cluster_analysis.call_count > 0

    assert isinstance(spied_cluster_analysis.spy_return, Cluster)
    assert (
        spied_cluster_analysis.spy_return.total_number_of_machines()
        == expected_num_machines
    )


async def _test_cluster_scaling_up_and_down(  # noqa: PLR0915
    *,
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
    fake_node: Node,
    mock_rabbitmq_post_message: mock.Mock,
    mock_find_node_with_name_returns_fake_node: mock.Mock,
    mock_docker_set_node_availability: mock.Mock,
    mock_compute_node_used_resources: mock.Mock,
    mocker: MockerFixture,
    async_docker_client: aiodocker.Docker,
    with_drain_nodes_labelled: bool,
    ec2_instance_custom_tags: dict[str, str],
    scale_up_params: _ScaleUpParams,
    instance_type_filters: Sequence[FilterTypeDef],
    run_against_moto: bool,
    spied_cluster_analysis: MockType,
):
    # we have nothing running now
    all_instances = await ec2_client.describe_instances(Filters=instance_type_filters)
    assert not all_instances["Reservations"]

    assert (
        scale_up_params.expected_num_instances == 1
    ), "This test is not made to work with more than 1 expected instance. so please adapt if needed"

    # create the service(s)
    created_docker_services = await asyncio.gather(
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

    # this should trigger a scaling up as we have no nodes
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )
    _assert_cluster_state(
        spied_cluster_analysis, expected_calls=1, expected_num_machines=0
    )

    with log_context(logging.INFO, "wait for EC2 instances to be running") as ctx:

        @tenacity.retry(
            wait=tenacity.wait_fixed(5),
            stop=tenacity.stop_after_delay(5 if run_against_moto else 120),
            retry=tenacity.retry_if_exception_type(AssertionError),
            reraise=True,
            before_sleep=tenacity.before_sleep_log(ctx.logger, logging.INFO),
            after=tenacity.after_log(ctx.logger, logging.INFO),
        )
        async def _assert_wait_for_ec2_instances_running() -> list[InstanceTypeDef]:
            # check the instance was started and we have exactly 1
            instances = await assert_autoscaled_dynamic_ec2_instances(
                ec2_client,
                expected_num_reservations=1,
                expected_num_instances=scale_up_params.expected_num_instances,
                expected_instance_type=scale_up_params.expected_instance_type,
                expected_instance_state="running",
                expected_additional_tag_keys=list(ec2_instance_custom_tags),
                instance_filters=instance_type_filters,
            )

            # as the new node is already running, but is not yet connected, hence not tagged and drained
            mock_find_node_with_name_returns_fake_node.assert_not_called()
            mock_docker_tag_node.assert_not_called()
            mock_docker_set_node_availability.assert_not_called()
            mock_compute_node_used_resources.assert_not_called()
            # check rabbit messages were sent
            _assert_rabbit_autoscaling_message_sent(
                mock_rabbitmq_post_message,
                app_settings,
                initialized_app,
                instances_running=0,
                instances_pending=scale_up_params.expected_num_instances,
            )
            mock_rabbitmq_post_message.reset_mock()

            return instances

        created_instances = await _assert_wait_for_ec2_instances_running()

    # 2. running this again should not scale again, but tag the node and make it available
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )
    _assert_cluster_state(
        spied_cluster_analysis, expected_calls=1, expected_num_machines=1
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
    } | {
        DOCKER_TASK_EC2_INSTANCE_TYPE_PLACEMENT_CONSTRAINT_KEY: scale_up_params.expected_instance_type
    }
    fake_attached_node.Spec.Labels |= expected_docker_node_tags | {
        _OSPARC_SERVICE_READY_LABEL_KEY: "false"
    }

    # the node is tagged and made active right away since we still have the pending task
    mock_find_node_with_name_returns_fake_node.assert_called_once()
    mock_find_node_with_name_returns_fake_node.reset_mock()

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
    instances = await assert_autoscaled_dynamic_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=scale_up_params.expected_num_instances,
        expected_instance_type=scale_up_params.expected_instance_type,
        expected_instance_state="running",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
        instance_filters=instance_type_filters,
    )
    assert created_instances == instances
    assert len(instances) == scale_up_params.expected_num_instances
    assert "PrivateDnsName" in instances[0]
    internal_dns_name = instances[0]["PrivateDnsName"].removesuffix(".ec2.internal")

    # check rabbit messages were sent, we do have worker
    assert fake_attached_node.Description
    assert fake_attached_node.Description.Resources
    assert fake_attached_node.Description.Resources.NanoCPUs
    _assert_rabbit_autoscaling_message_sent(
        mock_rabbitmq_post_message,
        app_settings,
        initialized_app,
        nodes_total=scale_up_params.expected_num_instances,
        nodes_active=scale_up_params.expected_num_instances,
        cluster_total_resources={
            "cpus": fake_attached_node.Description.Resources.NanoCPUs / 1e9,
            "ram": fake_attached_node.Description.Resources.MemoryBytes,
        },
        cluster_used_resources={
            "cpus": float(0),
            "ram": 0,
        },
        instances_running=scale_up_params.expected_num_instances,
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
    mock_find_node_with_name_returns_fake_node.assert_not_called()
    mock_docker_tag_node.assert_not_called()
    mock_docker_set_node_availability.assert_not_called()
    # check the number of instances did not change and is still running
    instances = await assert_autoscaled_dynamic_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=scale_up_params.expected_num_instances,
        expected_instance_type=scale_up_params.expected_instance_type,
        expected_instance_state="running",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
        instance_filters=instance_type_filters,
    )
    assert created_instances == instances

    # check rabbit messages were sent
    mock_rabbitmq_post_message.assert_called()
    assert mock_rabbitmq_post_message.call_count == num_useless_calls
    mock_rabbitmq_post_message.reset_mock()

    #
    # 4. now scaling down by removing the docker service
    #
    await asyncio.gather(
        *(
            async_docker_client.services.delete(d.ID)
            for d in created_docker_services
            if d.ID
        )
    )

    await auto_scale_cluster(app=initialized_app, auto_scaling_mode=auto_scaling_mode)
    # check the number of instances did not change and is still running
    instances = await assert_autoscaled_dynamic_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=scale_up_params.expected_num_instances,
        expected_instance_type=scale_up_params.expected_instance_type,
        expected_instance_state="running",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
        instance_filters=instance_type_filters,
    )
    assert created_instances == instances
    # the node shall be waiting before draining
    mock_docker_set_node_availability.assert_not_called()
    mock_docker_tag_node.assert_called_once_with(
        get_docker_client(initialized_app),
        fake_attached_node,
        tags=fake_attached_node.Spec.Labels
        | {
            _OSPARC_NODE_EMPTY_DATETIME_LABEL_KEY: mock.ANY,
        },
        available=True,
    )
    mock_docker_tag_node.reset_mock()

    # now update the fake node to have the required label as expected
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    fake_attached_node.Spec.Labels[_OSPARC_NODE_EMPTY_DATETIME_LABEL_KEY] = (
        arrow.utcnow()
        .shift(
            seconds=-app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_DRAINING.total_seconds()
            - 1
        )
        .datetime.isoformat()
    )

    # now it will drain
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

    instances = await assert_autoscaled_dynamic_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=scale_up_params.expected_num_instances,
        expected_instance_type=scale_up_params.expected_instance_type,
        expected_instance_state="running",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
        instance_filters=instance_type_filters,
    )
    assert created_instances == instances

    # we artifically set the node to drain
    if not with_drain_nodes_labelled:
        fake_attached_node.Spec.Availability = Availability.drain
    fake_attached_node.Spec.Labels[_OSPARC_SERVICE_READY_LABEL_KEY] = "false"
    fake_attached_node.Spec.Labels[
        _OSPARC_SERVICES_READY_DATETIME_LABEL_KEY
    ] = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()

    # the node will not be terminated before the timeout triggers
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
    instances = await assert_autoscaled_dynamic_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=scale_up_params.expected_num_instances,
        expected_instance_type=scale_up_params.expected_instance_type,
        expected_instance_state="running",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
        instance_filters=instance_type_filters,
    )
    assert created_instances == instances

    # now changing the last update timepoint will trigger the node removal process
    fake_attached_node.Spec.Labels[_OSPARC_SERVICES_READY_DATETIME_LABEL_KEY] = (
        datetime.datetime.now(tz=datetime.timezone.utc)
        - app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
        - datetime.timedelta(seconds=1)
    ).isoformat()
    # first making sure the node is drained, then terminate it after a delay to let it drain
    await auto_scale_cluster(app=initialized_app, auto_scaling_mode=auto_scaling_mode)
    mocked_docker_remove_node.assert_not_called()
    instances = await assert_autoscaled_dynamic_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=scale_up_params.expected_num_instances,
        expected_instance_type=scale_up_params.expected_instance_type,
        expected_instance_state="running",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
        instance_filters=instance_type_filters,
    )
    assert created_instances == instances
    mock_docker_tag_node.assert_called_once_with(
        get_docker_client(initialized_app),
        fake_attached_node,
        tags=fake_attached_node.Spec.Labels
        | {
            _OSPARC_NODE_TERMINATION_PROCESS_LABEL_KEY: mock.ANY,
        },
        available=False,
    )
    mock_docker_tag_node.reset_mock()
    # set the fake node to drain
    fake_attached_node.Spec.Availability = Availability.drain
    fake_attached_node.Spec.Labels[_OSPARC_NODE_TERMINATION_PROCESS_LABEL_KEY] = (
        arrow.utcnow()
        .shift(
            seconds=-app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_FINAL_TERMINATION.total_seconds()
            - 1
        )
        .datetime.isoformat()
    )

    await auto_scale_cluster(app=initialized_app, auto_scaling_mode=auto_scaling_mode)
    mocked_docker_remove_node.assert_called_once_with(
        mock.ANY, nodes=[fake_attached_node], force=True
    )
    # we need to check for the right instance here

    with log_context(logging.INFO, "wait for EC2 instances to be terminated") as ctx:

        @tenacity.retry(
            wait=tenacity.wait_fixed(5),
            stop=tenacity.stop_after_delay(5 if run_against_moto else 120),
            retry=tenacity.retry_if_exception_type(AssertionError),
            reraise=True,
            before_sleep=tenacity.before_sleep_log(ctx.logger, logging.INFO),
            after=tenacity.after_log(ctx.logger, logging.INFO),
        )
        async def _assert_wait_for_ec2_instances_terminated() -> None:
            assert created_instances[0]
            assert "InstanceId" in created_instances[0]
            await assert_autoscaled_dynamic_ec2_instances(
                ec2_client,
                expected_num_reservations=1,
                expected_num_instances=scale_up_params.expected_num_instances,
                expected_instance_type=scale_up_params.expected_instance_type,
                expected_instance_state="terminated",
                expected_additional_tag_keys=list(ec2_instance_custom_tags),
                instance_filters=[
                    FilterTypeDef(
                        Name="instance-id", Values=[created_instances[0]["InstanceId"]]
                    )
                ],
            )

        await _assert_wait_for_ec2_instances_terminated()


@pytest.mark.acceptance_test()
@pytest.mark.parametrize(
    "scale_up_params",
    [
        pytest.param(
            _ScaleUpParams(
                imposed_instance_type=None,
                service_resources=Resources(
                    cpus=4, ram=parse_obj_as(ByteSize, "128Gib")
                ),
                num_services=1,
                expected_instance_type="r5n.4xlarge",
                expected_num_instances=1,
            ),
            id="No explicit instance defined",
        ),
        pytest.param(
            _ScaleUpParams(
                imposed_instance_type="t2.xlarge",
                service_resources=Resources(cpus=4, ram=parse_obj_as(ByteSize, "4Gib")),
                num_services=1,
                expected_instance_type="t2.xlarge",
                expected_num_instances=1,
            ),
            id="Explicitely ask for t2.xlarge",
        ),
        pytest.param(
            _ScaleUpParams(
                imposed_instance_type="r5n.8xlarge",
                service_resources=Resources(
                    cpus=4, ram=parse_obj_as(ByteSize, "128Gib")
                ),
                num_services=1,
                expected_instance_type="r5n.8xlarge",
                expected_num_instances=1,
            ),
            id="Explicitely ask for r5n.8xlarge",
        ),
    ],
)
async def test_cluster_scaling_up_and_down(
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
    fake_node: Node,
    mock_rabbitmq_post_message: mock.Mock,
    mock_find_node_with_name_returns_fake_node: mock.Mock,
    mock_docker_set_node_availability: mock.Mock,
    mock_compute_node_used_resources: mock.Mock,
    mocker: MockerFixture,
    async_docker_client: aiodocker.Docker,
    with_drain_nodes_labelled: bool,
    ec2_instance_custom_tags: dict[str, str],
    instance_type_filters: Sequence[FilterTypeDef],
    scale_up_params: _ScaleUpParams,
    spied_cluster_analysis: MockType,
):
    await _test_cluster_scaling_up_and_down(
        service_monitored_labels=service_monitored_labels,
        osparc_docker_label_keys=osparc_docker_label_keys,
        app_settings=app_settings,
        initialized_app=initialized_app,
        create_service=create_service,
        task_template=task_template,
        create_task_reservations=create_task_reservations,
        ec2_client=ec2_client,
        mock_docker_tag_node=mock_docker_tag_node,
        fake_node=fake_node,
        mock_rabbitmq_post_message=mock_rabbitmq_post_message,
        mock_find_node_with_name_returns_fake_node=mock_find_node_with_name_returns_fake_node,
        mock_docker_set_node_availability=mock_docker_set_node_availability,
        mock_compute_node_used_resources=mock_compute_node_used_resources,
        mocker=mocker,
        async_docker_client=async_docker_client,
        with_drain_nodes_labelled=with_drain_nodes_labelled,
        ec2_instance_custom_tags=ec2_instance_custom_tags,
        scale_up_params=scale_up_params,
        instance_type_filters=instance_type_filters,
        run_against_moto=True,
        spied_cluster_analysis=spied_cluster_analysis,
    )


@pytest.mark.parametrize(
    "scale_up_params",
    [
        pytest.param(
            _ScaleUpParams(
                imposed_instance_type=None,
                service_resources=Resources(
                    cpus=4, ram=parse_obj_as(ByteSize, "62Gib")
                ),
                num_services=1,
                expected_instance_type="r6a.2xlarge",
                expected_num_instances=1,
            ),
            id="No explicit instance defined",
        ),
    ],
)
async def test_cluster_scaling_up_and_down_against_aws(
    skip_if_external_envfile_dict: None,
    external_ec2_instances_allowed_types: None | dict[str, EC2InstanceBootSpecific],
    with_labelize_drain_nodes: EnvVarsDict,
    docker_swarm: None,
    disabled_rabbitmq: None,
    disable_dynamic_service_background_task: None,
    disable_buffers_pool_background_task: None,
    mocked_redis_server: None,
    external_envfile_dict: EnvVarsDict,
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
    fake_node: Node,
    mock_rabbitmq_post_message: mock.Mock,
    mock_find_node_with_name_returns_fake_node: mock.Mock,
    mock_docker_set_node_availability: mock.Mock,
    mock_compute_node_used_resources: mock.Mock,
    mocker: MockerFixture,
    async_docker_client: aiodocker.Docker,
    with_drain_nodes_labelled: bool,
    ec2_instance_custom_tags: dict[str, str],
    instance_type_filters: Sequence[FilterTypeDef],
    scale_up_params: _ScaleUpParams,
    spied_cluster_analysis: MockType,
):
    # ensure we run a test that makes sense
    assert external_ec2_instances_allowed_types
    assert (
        scale_up_params.expected_instance_type in external_ec2_instances_allowed_types
    ), (
        f"ensure the expected created instance is at least allowed: you expect {scale_up_params.expected_instance_type}"
        f" The passed external ENV allows for {list(external_ec2_instances_allowed_types)}"
    )
    await _test_cluster_scaling_up_and_down(
        service_monitored_labels=service_monitored_labels,
        osparc_docker_label_keys=osparc_docker_label_keys,
        app_settings=app_settings,
        initialized_app=initialized_app,
        create_service=create_service,
        task_template=task_template,
        create_task_reservations=create_task_reservations,
        ec2_client=ec2_client,
        mock_docker_tag_node=mock_docker_tag_node,
        fake_node=fake_node,
        mock_rabbitmq_post_message=mock_rabbitmq_post_message,
        mock_find_node_with_name_returns_fake_node=mock_find_node_with_name_returns_fake_node,
        mock_docker_set_node_availability=mock_docker_set_node_availability,
        mock_compute_node_used_resources=mock_compute_node_used_resources,
        mocker=mocker,
        async_docker_client=async_docker_client,
        with_drain_nodes_labelled=with_drain_nodes_labelled,
        ec2_instance_custom_tags=ec2_instance_custom_tags,
        scale_up_params=scale_up_params,
        instance_type_filters=instance_type_filters,
        run_against_moto=False,
        spied_cluster_analysis=spied_cluster_analysis,
    )


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
    patch_ec2_client_launch_instancess_min_number_of_instances: mock.Mock,
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
    mock_find_node_with_name_returns_fake_node: mock.Mock,
    mock_docker_set_node_availability: mock.Mock,
    ec2_instance_custom_tags: dict[str, str],
    instance_type_filters: Sequence[FilterTypeDef],
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
    await assert_autoscaled_dynamic_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=scale_up_params.expected_num_instances,
        expected_instance_type=scale_up_params.expected_instance_type,
        expected_instance_state="running",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
        instance_filters=instance_type_filters,
    )

    # as the new node is already running, but is not yet connected, hence not tagged and drained
    mock_find_node_with_name_returns_fake_node.assert_not_called()
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


@pytest.mark.parametrize(
    "docker_service_imposed_ec2_type, docker_service_ram, expected_ec2_type",
    [
        pytest.param(
            None,
            parse_obj_as(ByteSize, "128Gib"),
            "r5n.4xlarge",
            id="No explicit instance defined",
        ),
    ],
)
async def test_long_pending_ec2_is_detected_as_broken_terminated_and_restarted(
    with_short_ec2_instances_max_start_time: EnvVarsDict,
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
    docker_service_imposed_ec2_type: InstanceTypeType | None,
    docker_service_ram: ByteSize,
    expected_ec2_type: InstanceTypeType,
    mock_find_node_with_name_returns_none: mock.Mock,
    mock_docker_tag_node: mock.Mock,
    mock_rabbitmq_post_message: mock.Mock,
    short_ec2_instance_max_start_time: datetime.timedelta,
    ec2_instance_custom_tags: dict[str, str],
    instance_type_filters: Sequence[FilterTypeDef],
):
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    assert (
        short_ec2_instance_max_start_time
        == app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_START_TIME
    )
    # we have nothing running now
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]
    # create a service
    await create_service(
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
    instances = await assert_autoscaled_dynamic_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=1,
        expected_instance_type=expected_ec2_type,
        expected_instance_state="running",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
        instance_filters=instance_type_filters,
    )

    # as the new node is already running, but is not yet connected, hence not tagged and drained
    mock_find_node_with_name_returns_none.assert_not_called()
    mock_docker_tag_node.assert_not_called()
    # check rabbit messages were sent
    _assert_rabbit_autoscaling_message_sent(
        mock_rabbitmq_post_message,
        app_settings,
        initialized_app,
        instances_running=0,
        instances_pending=1,
    )
    mock_rabbitmq_post_message.reset_mock()

    assert instances
    assert "LaunchTime" in instances[0]
    original_instance_launch_time: datetime.datetime = deepcopy(
        instances[0]["LaunchTime"]
    )
    await asyncio.sleep(1)  # NOTE: we wait here since AWS does not keep microseconds
    now = arrow.utcnow().datetime

    assert now > original_instance_launch_time
    assert now < (
        original_instance_launch_time
        + app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_START_TIME
    )

    # 2. running again several times the autoscaler, the node does not join
    for i in range(7):
        await auto_scale_cluster(
            app=initialized_app, auto_scaling_mode=DynamicAutoscaling()
        )
        # there should be no scaling up, since there is already a pending instance
        instances = await assert_autoscaled_dynamic_ec2_instances(
            ec2_client,
            expected_num_reservations=1,
            expected_num_instances=1,
            expected_instance_type=expected_ec2_type,
            expected_instance_state="running",
            expected_additional_tag_keys=list(ec2_instance_custom_tags),
            instance_filters=instance_type_filters,
        )
        assert mock_find_node_with_name_returns_none.call_count == i + 1
        mock_docker_tag_node.assert_not_called()
        _assert_rabbit_autoscaling_message_sent(
            mock_rabbitmq_post_message,
            app_settings,
            initialized_app,
            instances_running=0,
            instances_pending=1,
        )
        mock_rabbitmq_post_message.reset_mock()
        assert instances
        assert "LaunchTime" in instances[0]
        assert instances[0]["LaunchTime"] == original_instance_launch_time

    # 3. wait for the instance max start time and try again, shall terminate the instance
    now = arrow.utcnow().datetime
    sleep_time = (
        original_instance_launch_time
        + app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_START_TIME
        - now
    ).total_seconds() + 1
    print(
        f"--> waiting now for {sleep_time}s for the pending EC2 to be deemed as unworthy"
    )
    await asyncio.sleep(sleep_time)
    now = arrow.utcnow().datetime
    assert now > (
        original_instance_launch_time
        + app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_START_TIME
    )
    # scaling now will terminate the broken ec2 that did not connect, and directly create a replacement
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )
    # we have therefore 2 reservations, first instance is terminated and a second one started
    all_instances = await ec2_client.describe_instances()
    assert len(all_instances["Reservations"]) == 2
    assert "Instances" in all_instances["Reservations"][0]
    assert len(all_instances["Reservations"][0]["Instances"]) == 1
    assert "State" in all_instances["Reservations"][0]["Instances"][0]
    assert "Name" in all_instances["Reservations"][0]["Instances"][0]["State"]
    assert (
        all_instances["Reservations"][0]["Instances"][0]["State"]["Name"]
        == "terminated"
    )

    assert "Instances" in all_instances["Reservations"][1]
    assert len(all_instances["Reservations"][1]["Instances"]) == 1
    assert "State" in all_instances["Reservations"][1]["Instances"][0]
    assert "Name" in all_instances["Reservations"][1]["Instances"][0]["State"]
    assert (
        all_instances["Reservations"][1]["Instances"][0]["State"]["Name"] == "running"
    )


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
    instance_type_filters: Sequence[FilterTypeDef],
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
