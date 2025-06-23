# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import datetime
import logging
import random
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
    DockerGenericTag,
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
from pydantic import ByteSize, TypeAdapter
from pytest_mock import MockType
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.autoscaling import (
    assert_cluster_state,
    create_fake_association,
)
from pytest_simcore.helpers.aws_ec2 import (
    assert_autoscaled_dynamic_ec2_instances,
    assert_autoscaled_dynamic_warm_pools_ec2_instances,
)
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from simcore_service_autoscaling.constants import BUFFER_MACHINE_TAG_KEY
from simcore_service_autoscaling.core.settings import ApplicationSettings
from simcore_service_autoscaling.models import AssociatedInstance, Cluster
from simcore_service_autoscaling.modules.cluster_scaling._auto_scaling_core import (
    _activate_drained_nodes,
    _find_terminateable_instances,
    _try_scale_down_cluster,
    auto_scale_cluster,
)
from simcore_service_autoscaling.modules.cluster_scaling.auto_scaling_mode_dynamic import (
    DynamicAutoscaling,
)
from simcore_service_autoscaling.modules.docker import (
    AutoscalingDocker,
    get_docker_client,
)
from simcore_service_autoscaling.utils.auto_scaling_core import (
    node_host_name_from_ec2_private_dns,
)
from simcore_service_autoscaling.utils.utils_docker import (
    _OSPARC_NODE_EMPTY_DATETIME_LABEL_KEY,
    _OSPARC_NODE_TERMINATION_PROCESS_LABEL_KEY,
    _OSPARC_SERVICE_READY_LABEL_KEY,
    _OSPARC_SERVICES_READY_DATETIME_LABEL_KEY,
)
from types_aiobotocore_ec2.client import EC2Client
from types_aiobotocore_ec2.literals import InstanceStateNameType, InstanceTypeType
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
    return TypeAdapter(datetime.timedelta).validate_python(time)


@pytest.fixture
async def drained_host_node(
    host_node: Node, async_docker_client: aiodocker.Docker
) -> AsyncIterator[Node]:
    assert host_node.id
    assert host_node.version
    assert host_node.version.index
    assert host_node.spec
    assert host_node.spec.availability
    assert host_node.spec.role

    old_availability = host_node.spec.availability
    await async_docker_client.nodes.update(
        node_id=host_node.id,
        version=host_node.version.index,
        spec={
            "Availability": "drain",
            "Labels": host_node.spec.labels,
            "Role": host_node.spec.role.value,
        },
    )
    drained_node = TypeAdapter(Node).validate_python(
        await async_docker_client.nodes.inspect(node_id=host_node.id)
    )
    yield drained_node
    # revert
    # NOTE: getting the node again as the version might have changed
    drained_node = TypeAdapter(Node).validate_python(
        await async_docker_client.nodes.inspect(node_id=host_node.id)
    )
    assert drained_node.id
    assert drained_node.version
    assert drained_node.version.index
    assert drained_node.spec
    assert drained_node.spec.role
    await async_docker_client.nodes.update(
        node_id=drained_node.id,
        version=drained_node.version.index,
        spec={
            "Availability": old_availability.value,
            "Labels": drained_node.spec.labels,
            "Role": drained_node.spec.role.value,
        },
    )


@pytest.fixture
def minimal_configuration(
    with_labelize_drain_nodes: EnvVarsDict,
    app_with_docker_join_drained: EnvVarsDict,
    docker_swarm: None,
    mocked_ec2_server_envs: EnvVarsDict,
    mocked_ssm_server_envs: EnvVarsDict,
    enabled_dynamic_mode: EnvVarsDict,
    mocked_ec2_instances_envs: EnvVarsDict,
    disabled_rabbitmq: None,
    disable_autoscaling_background_task: None,
    disable_buffers_pool_background_task: None,
    mocked_redis_server: None,
) -> None: ...


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
        cluster_total_resources=Resources.create_as_empty().model_dump(),
        cluster_used_resources=Resources.create_as_empty().model_dump(),
        instances_pending=0,
        instances_running=0,
    )
    expected_message = default_message.model_copy(update=message_update_kwargs)
    assert mock_rabbitmq_post_message.call_args == mock.call(app, expected_message)


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
def stopped_instance_type_filters(
    instance_type_filters: Sequence[FilterTypeDef],
) -> Sequence[FilterTypeDef]:
    copied_filters = deepcopy(instance_type_filters)
    copied_filters[-1]["Values"] = ["stopped"]
    return copied_filters


@dataclass(frozen=True)
class _ScaleUpParams:
    imposed_instance_type: InstanceTypeType | None
    service_resources: Resources
    num_services: int
    expected_instance_type: InstanceTypeType
    expected_num_instances: int


@pytest.fixture
async def create_services_batch(
    create_service: Callable[
        [dict[str, Any], dict[DockerLabelKey, str], str, list[str]], Awaitable[Service]
    ],
    task_template: dict[str, Any],
    create_task_reservations: Callable[[int, int], dict[str, Any]],
    service_monitored_labels: dict[DockerLabelKey, str],
    osparc_docker_label_keys: StandardSimcoreDockerLabels,
) -> Callable[[_ScaleUpParams], Awaitable[list[Service]]]:
    async def _(scale_up_params: _ScaleUpParams) -> list[Service]:
        return await asyncio.gather(
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

    return _


@pytest.mark.parametrize(
    # NOTE: only the main test test_cluster_scaling_up_and_down is run with all options
    "with_docker_join_drained",
    ["without_AUTOSCALING_DOCKER_JOIN_DRAINED"],
    indirect=True,
)
@pytest.mark.parametrize(
    # NOTE: only the main test test_cluster_scaling_up_and_down is run with all options
    "with_drain_nodes_labelled",
    ["with_AUTOSCALING_DRAIN_NODES_WITH_LABELS"],
    indirect=True,
)
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


@pytest.mark.parametrize(
    # NOTE: only the main test test_cluster_scaling_up_and_down is run with all options
    "with_docker_join_drained",
    ["without_AUTOSCALING_DOCKER_JOIN_DRAINED"],
    indirect=True,
)
@pytest.mark.parametrize(
    # NOTE: only the main test test_cluster_scaling_up_and_down is run with all options
    "with_drain_nodes_labelled",
    ["with_AUTOSCALING_DRAIN_NODES_WITH_LABELS"],
    indirect=True,
)
async def test_cluster_scaling_with_no_services_and_machine_buffer_starts_expected_machines(
    patch_ec2_client_launch_instances_min_number_of_instances: mock.Mock,
    minimal_configuration: None,
    with_instances_machines_hot_buffer: EnvVarsDict,
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
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )
    await assert_autoscaled_dynamic_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER,
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
        instances_pending=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER,
    )
    mock_rabbitmq_post_message.reset_mock()
    # calling again should attach the new nodes to the reserve, but nothing should start
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )
    await assert_autoscaled_dynamic_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER,
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
    assert fake_node.description
    assert fake_node.description.resources
    assert fake_node.description.resources.nano_cp_us
    assert fake_node.description.resources.memory_bytes
    _assert_rabbit_autoscaling_message_sent(
        mock_rabbitmq_post_message,
        app_settings,
        initialized_app,
        nodes_total=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER,
        nodes_drained=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER,
        instances_running=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER,
        cluster_total_resources={
            "cpus": app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER
            * fake_node.description.resources.nano_cp_us
            / 1e9,
            "ram": app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER
            * fake_node.description.resources.memory_bytes,
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
        expected_num_instances=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER,
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


@pytest.mark.parametrize(
    # NOTE: only the main test test_cluster_scaling_up_and_down is run with all options
    "with_docker_join_drained",
    ["without_AUTOSCALING_DOCKER_JOIN_DRAINED"],
    indirect=True,
)
@pytest.mark.parametrize(
    # NOTE: only the main test test_cluster_scaling_up_and_down is run with all options
    "with_drain_nodes_labelled",
    ["with_AUTOSCALING_DRAIN_NODES_WITH_LABELS"],
    indirect=True,
)
@pytest.mark.parametrize(
    "scale_up_params",
    [
        pytest.param(
            _ScaleUpParams(
                imposed_instance_type=None,
                service_resources=Resources(
                    cpus=4, ram=TypeAdapter(ByteSize).validate_python("128000Gib")
                ),
                num_services=1,
                expected_instance_type="r5n.4xlarge",
                expected_num_instances=1,
            ),
            id="No explicit instance defined",
        ),
    ],
)
async def test_cluster_scaling_with_service_asking_for_too_much_resources_starts_nothing(
    minimal_configuration: None,
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    create_services_batch: Callable[[_ScaleUpParams], Awaitable[list[Service]]],
    mock_launch_instances: mock.Mock,
    mock_terminate_instances: mock.Mock,
    mock_rabbitmq_post_message: mock.Mock,
    scale_up_params: _ScaleUpParams,
):
    await create_services_batch(scale_up_params)

    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )
    mock_launch_instances.assert_not_called()
    mock_terminate_instances.assert_not_called()
    _assert_rabbit_autoscaling_message_sent(
        mock_rabbitmq_post_message, app_settings, initialized_app
    )


async def _test_cluster_scaling_up_and_down(  # noqa: PLR0915
    *,
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    create_services_batch: Callable[[_ScaleUpParams], Awaitable[list[Service]]],
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

    assert scale_up_params.expected_num_instances == 1, (
        "This test is not made to work with more than 1 expected instance. so please adapt if needed"
    )

    # create the service(s)
    created_docker_services = await create_services_batch(scale_up_params)

    # this should trigger a scaling up as we have no nodes
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )
    assert_cluster_state(
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
    assert_cluster_state(
        spied_cluster_analysis, expected_calls=1, expected_num_machines=1
    )

    fake_attached_node = deepcopy(fake_node)
    assert fake_attached_node.spec
    fake_attached_node.spec.availability = (
        Availability.active if with_drain_nodes_labelled else Availability.drain
    )
    assert fake_attached_node.spec.labels
    assert app_settings.AUTOSCALING_NODES_MONITORING
    expected_docker_node_tags = dict.fromkeys(
        app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS
        + app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NEW_NODES_LABELS,
        "true",
    ) | {
        DOCKER_TASK_EC2_INSTANCE_TYPE_PLACEMENT_CONSTRAINT_KEY: scale_up_params.expected_instance_type
    }
    fake_attached_node.spec.labels |= expected_docker_node_tags | {
        _OSPARC_SERVICE_READY_LABEL_KEY: "false"
    }

    # the node is tagged and made active right away since we still have the pending task
    mock_find_node_with_name_returns_fake_node.assert_called_once()
    mock_find_node_with_name_returns_fake_node.reset_mock()

    assert mock_docker_tag_node.call_count == 3
    assert fake_node.spec
    assert fake_node.spec.labels
    # check attach call
    assert mock_docker_tag_node.call_args_list[0] == mock.call(
        get_docker_client(initialized_app),
        fake_node,
        tags=fake_node.spec.labels
        | expected_docker_node_tags
        | {
            _OSPARC_SERVICE_READY_LABEL_KEY: "false",
            _OSPARC_SERVICES_READY_DATETIME_LABEL_KEY: mock.ANY,
        },
        available=with_drain_nodes_labelled,
    )
    # update our fake node
    fake_attached_node.spec.labels[_OSPARC_SERVICE_READY_LABEL_KEY] = "true"
    fake_attached_node.spec.labels[_OSPARC_SERVICES_READY_DATETIME_LABEL_KEY] = (
        mock_docker_tag_node.call_args_list[2][1]["tags"][
            _OSPARC_SERVICES_READY_DATETIME_LABEL_KEY
        ]
    )
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
    fake_attached_node.spec.availability = Availability.active
    mock_compute_node_used_resources.assert_called_once_with(
        get_docker_client(initialized_app),
        fake_attached_node,
    )
    mock_compute_node_used_resources.reset_mock()
    # check activate call

    assert mock_docker_tag_node.call_args_list[2] == mock.call(
        get_docker_client(initialized_app),
        fake_attached_node,
        tags=fake_node.spec.labels
        | expected_docker_node_tags
        | {
            _OSPARC_SERVICE_READY_LABEL_KEY: "true",
            _OSPARC_SERVICES_READY_DATETIME_LABEL_KEY: mock.ANY,
        },
        available=True,
    )
    # update our fake node
    fake_attached_node.spec.labels[_OSPARC_SERVICES_READY_DATETIME_LABEL_KEY] = (
        mock_docker_tag_node.call_args_list[1][1]["tags"][
            _OSPARC_SERVICES_READY_DATETIME_LABEL_KEY
        ]
    )
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
    assert fake_attached_node.description
    assert fake_attached_node.description.resources
    assert fake_attached_node.description.resources.nano_cp_us
    _assert_rabbit_autoscaling_message_sent(
        mock_rabbitmq_post_message,
        app_settings,
        initialized_app,
        nodes_total=scale_up_params.expected_num_instances,
        nodes_active=scale_up_params.expected_num_instances,
        cluster_total_resources={
            "cpus": fake_attached_node.description.resources.nano_cp_us / 1e9,
            "ram": fake_attached_node.description.resources.memory_bytes,
        },
        cluster_used_resources={
            "cpus": float(0),
            "ram": 0,
        },
        instances_running=scale_up_params.expected_num_instances,
    )
    mock_rabbitmq_post_message.reset_mock()

    # now we have 1 monitored node that needs to be mocked
    fake_attached_node.spec.labels[_OSPARC_SERVICE_READY_LABEL_KEY] = "true"
    fake_attached_node.status = NodeStatus(
        state=NodeState.ready, message=None, addr=None
    )
    fake_attached_node.spec.availability = Availability.active
    fake_attached_node.description.hostname = internal_dns_name

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
    assert mock_docker_tag_node.call_count == num_useless_calls
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

    # check rabbit messages were sent
    mock_rabbitmq_post_message.assert_called()
    assert mock_rabbitmq_post_message.call_count == num_useless_calls
    mock_rabbitmq_post_message.reset_mock()

    #
    # 4. now scaling down by removing the docker service
    #
    await asyncio.gather(
        *(
            async_docker_client.services.delete(d.id)
            for d in created_docker_services
            if d.id
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
        tags=fake_attached_node.spec.labels
        | {
            _OSPARC_NODE_EMPTY_DATETIME_LABEL_KEY: mock.ANY,
        },
        available=True,
    )
    mock_docker_tag_node.reset_mock()

    # now update the fake node to have the required label as expected
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    fake_attached_node.spec.labels[_OSPARC_NODE_EMPTY_DATETIME_LABEL_KEY] = (
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
        tags=fake_attached_node.spec.labels
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
        fake_attached_node.spec.labels[_OSPARC_SERVICES_READY_DATETIME_LABEL_KEY]
    )
    mock_docker_tag_node.reset_mock()

    # calling again does the exact same
    await auto_scale_cluster(app=initialized_app, auto_scaling_mode=auto_scaling_mode)
    mock_docker_set_node_availability.assert_not_called()
    mock_docker_tag_node.assert_called_once_with(
        get_docker_client(initialized_app),
        fake_attached_node,
        tags=fake_attached_node.spec.labels
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
        fake_attached_node.spec.availability = Availability.drain
    fake_attached_node.spec.labels[_OSPARC_SERVICE_READY_LABEL_KEY] = "false"
    fake_attached_node.spec.labels[_OSPARC_SERVICES_READY_DATETIME_LABEL_KEY] = (
        datetime.datetime.now(tz=datetime.UTC).isoformat()
    )

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
    fake_attached_node.spec.labels[_OSPARC_SERVICES_READY_DATETIME_LABEL_KEY] = (
        datetime.datetime.now(tz=datetime.UTC)
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
        tags=fake_attached_node.spec.labels
        | {
            _OSPARC_NODE_TERMINATION_PROCESS_LABEL_KEY: mock.ANY,
        },
        available=False,
    )
    mock_docker_tag_node.reset_mock()
    # set the fake node to drain
    fake_attached_node.spec.availability = Availability.drain
    fake_attached_node.spec.labels[_OSPARC_NODE_TERMINATION_PROCESS_LABEL_KEY] = (
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


@pytest.mark.acceptance_test
@pytest.mark.parametrize(
    "scale_up_params",
    [
        pytest.param(
            _ScaleUpParams(
                imposed_instance_type=None,
                service_resources=Resources(
                    cpus=4, ram=TypeAdapter(ByteSize).validate_python("128Gib")
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
                service_resources=Resources(
                    cpus=4, ram=TypeAdapter(ByteSize).validate_python("4Gib")
                ),
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
                    cpus=4, ram=TypeAdapter(ByteSize).validate_python("128Gib")
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
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    create_services_batch: Callable[[_ScaleUpParams], Awaitable[list[Service]]],
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
        app_settings=app_settings,
        initialized_app=initialized_app,
        create_services_batch=create_services_batch,
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
    # NOTE: only the main test test_cluster_scaling_up_and_down is run with all options
    "with_docker_join_drained",
    ["without_AUTOSCALING_DOCKER_JOIN_DRAINED"],
    indirect=True,
)
@pytest.mark.parametrize(
    # NOTE: only the main test test_cluster_scaling_up_and_down is run with all options
    "with_drain_nodes_labelled",
    ["with_AUTOSCALING_DRAIN_NODES_WITH_LABELS"],
    indirect=True,
)
@pytest.mark.parametrize(
    "scale_up_params",
    [
        pytest.param(
            _ScaleUpParams(
                imposed_instance_type=None,
                service_resources=Resources(
                    cpus=4, ram=TypeAdapter(ByteSize).validate_python("62Gib")
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
    skip_if_no_external_envfile: None,
    external_ec2_instances_allowed_types: None | dict[str, EC2InstanceBootSpecific],
    with_labelize_drain_nodes: EnvVarsDict,
    app_with_docker_join_drained: EnvVarsDict,
    docker_swarm: None,
    disabled_rabbitmq: None,
    disable_autoscaling_background_task: None,
    disable_buffers_pool_background_task: None,
    mocked_redis_server: None,
    external_envfile_dict: EnvVarsDict,
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    create_services_batch: Callable[[_ScaleUpParams], Awaitable[list[Service]]],
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
        app_settings=app_settings,
        initialized_app=initialized_app,
        create_services_batch=create_services_batch,
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
    # NOTE: only the main test test_cluster_scaling_up_and_down is run with all options
    "with_docker_join_drained",
    ["without_AUTOSCALING_DOCKER_JOIN_DRAINED"],
    indirect=True,
)
@pytest.mark.parametrize(
    # NOTE: only the main test test_cluster_scaling_up_and_down is run with all options
    "with_drain_nodes_labelled",
    ["with_AUTOSCALING_DRAIN_NODES_WITH_LABELS"],
    indirect=True,
)
@pytest.mark.parametrize(
    "scale_up_params",
    [
        pytest.param(
            _ScaleUpParams(
                imposed_instance_type=None,
                service_resources=Resources(
                    cpus=5, ram=TypeAdapter(ByteSize).validate_python("36Gib")
                ),
                num_services=10,
                expected_instance_type="r5n.4xlarge",  # 1 GPU, 16 CPUs, 128GiB
                expected_num_instances=4,
            ),
            id="sim4life-light",
        ),
        pytest.param(
            _ScaleUpParams(
                imposed_instance_type="g4dn.8xlarge",
                service_resources=Resources(
                    cpus=5, ram=TypeAdapter(ByteSize).validate_python("20480MB")
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
    patch_ec2_client_launch_instances_min_number_of_instances: mock.Mock,
    minimal_configuration: None,
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    create_services_batch: Callable[[_ScaleUpParams], Awaitable[list[Service]]],
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
    await create_services_batch(scale_up_params)

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
    # NOTE: only the main test test_cluster_scaling_up_and_down is run with all options
    "with_docker_join_drained",
    ["without_AUTOSCALING_DOCKER_JOIN_DRAINED"],
    indirect=True,
)
@pytest.mark.parametrize(
    # NOTE: only the main test test_cluster_scaling_up_and_down is run with all options
    "with_drain_nodes_labelled",
    ["with_AUTOSCALING_DRAIN_NODES_WITH_LABELS"],
    indirect=True,
)
@pytest.mark.parametrize(
    "scale_up_params1, scale_up_params2",
    [
        pytest.param(
            _ScaleUpParams(
                imposed_instance_type="g4dn.2xlarge",  # 1 GPU, 8 CPUs, 32GiB
                service_resources=Resources(
                    cpus=8, ram=TypeAdapter(ByteSize).validate_python("15Gib")
                ),
                num_services=12,
                expected_instance_type="g4dn.2xlarge",  # 1 GPU, 8 CPUs, 32GiB
                expected_num_instances=10,
            ),
            _ScaleUpParams(
                imposed_instance_type="g4dn.8xlarge",  # 32CPUs, 128GiB
                service_resources=Resources(
                    cpus=32, ram=TypeAdapter(ByteSize).validate_python("20480MB")
                ),
                num_services=7,
                expected_instance_type="g4dn.8xlarge",  # 32CPUs, 128GiB
                expected_num_instances=7,
            ),
            id="A batch of services requiring g3.4xlarge and a batch requiring g4dn.8xlarge",
        ),
    ],
)
async def test_cluster_adapts_machines_on_the_fly(  # noqa: PLR0915
    patch_ec2_client_launch_instances_min_number_of_instances: mock.Mock,
    minimal_configuration: None,
    ec2_client: EC2Client,
    initialized_app: FastAPI,
    app_settings: ApplicationSettings,
    create_services_batch: Callable[[_ScaleUpParams], Awaitable[list[Service]]],
    ec2_instance_custom_tags: dict[str, str],
    instance_type_filters: Sequence[FilterTypeDef],
    async_docker_client: aiodocker.Docker,
    scale_up_params1: _ScaleUpParams,
    scale_up_params2: _ScaleUpParams,
    mocked_associate_ec2_instances_with_nodes: mock.Mock,
    create_fake_node: Callable[..., Node],
    mock_docker_tag_node: mock.Mock,
    mock_compute_node_used_resources: mock.Mock,
    spied_cluster_analysis: MockType,
    mocker: MockerFixture,
):
    # pre-requisites
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    assert app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES > 0
    assert (
        scale_up_params1.num_services
        >= app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES
    ), (
        "this test requires to run a first batch of more services than the maximum number of instances allowed"
    )
    # we have nothing running now
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]

    #
    # 1. create the first batch of services requiring the initial machines
    first_batch_services = await create_services_batch(scale_up_params1)

    # it will only scale once and do nothing else
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )
    await assert_autoscaled_dynamic_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=scale_up_params1.expected_num_instances,
        expected_instance_type=scale_up_params1.expected_instance_type,
        expected_instance_state="running",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
        instance_filters=instance_type_filters,
    )
    assert_cluster_state(
        spied_cluster_analysis,
        expected_calls=1,
        expected_num_machines=0,
    )
    mocked_associate_ec2_instances_with_nodes.assert_called_once_with([], [])
    mocked_associate_ec2_instances_with_nodes.reset_mock()
    mocked_associate_ec2_instances_with_nodes.side_effect = create_fake_association(
        create_fake_node, None, None
    )

    #
    # 2. now the machines are associated
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )
    analyzed_cluster = assert_cluster_state(
        spied_cluster_analysis,
        expected_calls=1,
        expected_num_machines=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES,
    )
    mocked_associate_ec2_instances_with_nodes.assert_called_once()
    mock_docker_tag_node.assert_called()
    assert (
        mock_docker_tag_node.call_count
        == app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES
    )
    assert analyzed_cluster.active_nodes

    #
    # 3. now we start the second batch of services requiring a different type of machines
    await create_services_batch(scale_up_params2)

    # scaling will do nothing since we have hit the maximum number of machines
    for _ in range(3):
        await auto_scale_cluster(
            app=initialized_app, auto_scaling_mode=DynamicAutoscaling()
        )
        await assert_autoscaled_dynamic_ec2_instances(
            ec2_client,
            expected_num_reservations=1,
            expected_num_instances=scale_up_params1.expected_num_instances,
            expected_instance_type=scale_up_params1.expected_instance_type,
            expected_instance_state="running",
            expected_additional_tag_keys=list(ec2_instance_custom_tags),
            instance_filters=instance_type_filters,
        )

    analyzed_cluster = assert_cluster_state(
        spied_cluster_analysis,
        expected_calls=3,
        expected_num_machines=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES,
    )
    assert analyzed_cluster.active_nodes
    assert not analyzed_cluster.drained_nodes

    #
    # 4.now we simulate that some of the services in the 1st batch have completed and that we are 1 below the max
    # a machine should switch off and another type should be started
    completed_services_to_stop = random.sample(
        first_batch_services,
        scale_up_params1.num_services
        - app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES
        + 1,
    )
    await asyncio.gather(
        *(
            async_docker_client.services.delete(s.id)
            for s in completed_services_to_stop
            if s.id
        )
    )

    # first call to auto_scale_cluster will mark 1 node as empty
    with mock.patch(
        "simcore_service_autoscaling.modules.auto_scaling_core.utils_docker.set_node_found_empty",
        autospec=True,
    ) as mock_docker_set_node_found_empty:
        await auto_scale_cluster(
            app=initialized_app, auto_scaling_mode=DynamicAutoscaling()
        )
    analyzed_cluster = assert_cluster_state(
        spied_cluster_analysis,
        expected_calls=1,
        expected_num_machines=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES,
    )
    assert analyzed_cluster.active_nodes
    assert not analyzed_cluster.drained_nodes
    # the last machine is found empty
    mock_docker_set_node_found_empty.assert_called_with(
        mock.ANY,
        analyzed_cluster.active_nodes[-1].node,
        empty=True,
    )

    # now we mock the get_node_found_empty so the next call will actually drain the machine
    with mock.patch(
        "simcore_service_autoscaling.modules.auto_scaling_core.utils_docker.get_node_empty_since",
        autospec=True,
        return_value=arrow.utcnow().datetime
        - 1.5
        * app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_DRAINING,
    ) as mocked_get_node_empty_since:
        await auto_scale_cluster(
            app=initialized_app, auto_scaling_mode=DynamicAutoscaling()
        )
    mocked_get_node_empty_since.assert_called_once()
    analyzed_cluster = assert_cluster_state(
        spied_cluster_analysis,
        expected_calls=1,
        expected_num_machines=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES,
    )
    assert analyzed_cluster.active_nodes
    assert not analyzed_cluster.drained_nodes
    # now scaling again should find the drained machine
    drained_machine_instance_id = analyzed_cluster.active_nodes[-1].ec2_instance.id
    mocked_associate_ec2_instances_with_nodes.side_effect = create_fake_association(
        create_fake_node, drained_machine_instance_id, None
    )
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )
    analyzed_cluster = assert_cluster_state(
        spied_cluster_analysis,
        expected_calls=1,
        expected_num_machines=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES,
    )
    assert analyzed_cluster.active_nodes
    assert analyzed_cluster.drained_nodes

    # this will initiate termination now
    with mock.patch(
        "simcore_service_autoscaling.modules.auto_scaling_core.utils_docker.get_node_last_readyness_update",
        autospec=True,
        return_value=arrow.utcnow().datetime
        - 1.5
        * app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION,
    ):
        mock_docker_tag_node.reset_mock()
        await auto_scale_cluster(
            app=initialized_app, auto_scaling_mode=DynamicAutoscaling()
        )
    analyzed_cluster = assert_cluster_state(
        spied_cluster_analysis,
        expected_calls=1,
        expected_num_machines=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES,
    )
    mock_docker_tag_node.assert_called_with(
        mock.ANY,
        analyzed_cluster.drained_nodes[-1].node,
        tags=mock.ANY,
        available=False,
    )

    # scaling again should find the terminating machine
    mocked_associate_ec2_instances_with_nodes.side_effect = create_fake_association(
        create_fake_node, drained_machine_instance_id, drained_machine_instance_id
    )
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )
    analyzed_cluster = assert_cluster_state(
        spied_cluster_analysis,
        expected_calls=1,
        expected_num_machines=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES,
    )
    assert analyzed_cluster.active_nodes
    assert not analyzed_cluster.drained_nodes
    assert analyzed_cluster.terminating_nodes

    # now this will terminate it and straight away start a new machine type
    with mock.patch(
        "simcore_service_autoscaling.modules.auto_scaling_core.utils_docker.get_node_termination_started_since",
        autospec=True,
        return_value=arrow.utcnow().datetime
        - 1.5
        * app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION,
    ):
        mocked_docker_remove_node = mocker.patch(
            "simcore_service_autoscaling.modules.auto_scaling_core.utils_docker.remove_nodes",
            return_value=None,
            autospec=True,
        )
        await auto_scale_cluster(
            app=initialized_app, auto_scaling_mode=DynamicAutoscaling()
        )
        mocked_docker_remove_node.assert_called_once()

    # now let's check what we have
    all_instances = await ec2_client.describe_instances()
    assert len(all_instances["Reservations"]) == 2, "there should be 2 Reservations"
    reservation1 = all_instances["Reservations"][0]
    assert "Instances" in reservation1
    assert len(reservation1["Instances"]) == (
        app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES
    ), (
        f"expected {app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES} EC2 instances, found {len(reservation1['Instances'])}"
    )
    for instance in reservation1["Instances"]:
        assert "InstanceType" in instance
        assert instance["InstanceType"] == scale_up_params1.expected_instance_type
        assert "InstanceId" in instance
        assert "State" in instance
        assert "Name" in instance["State"]
        if instance["InstanceId"] == drained_machine_instance_id:
            assert instance["State"]["Name"] == "terminated"
        else:
            assert instance["State"]["Name"] == "running"

    reservation2 = all_instances["Reservations"][1]
    assert "Instances" in reservation2
    assert len(reservation2["Instances"]) == 1, (
        f"expected 1 EC2 instances, found {len(reservation2['Instances'])}"
    )
    for instance in reservation2["Instances"]:
        assert "InstanceType" in instance
        assert instance["InstanceType"] == scale_up_params2.expected_instance_type


@pytest.mark.parametrize(
    # NOTE: only the main test test_cluster_scaling_up_and_down is run with all options
    "with_docker_join_drained",
    ["without_AUTOSCALING_DOCKER_JOIN_DRAINED"],
    indirect=True,
)
@pytest.mark.parametrize(
    # NOTE: only the main test test_cluster_scaling_up_and_down is run with all options
    "with_drain_nodes_labelled",
    ["with_AUTOSCALING_DRAIN_NODES_WITH_LABELS"],
    indirect=True,
)
@pytest.mark.parametrize(
    "scale_up_params",
    [
        pytest.param(
            _ScaleUpParams(
                imposed_instance_type=None,
                service_resources=Resources(
                    cpus=4, ram=TypeAdapter(ByteSize).validate_python("128Gib")
                ),
                num_services=1,
                expected_instance_type="r5n.4xlarge",
                expected_num_instances=1,
            ),
            id="No explicit instance defined",
        ),
    ],
)
async def test_long_pending_ec2_is_detected_as_broken_terminated_and_restarted(
    with_short_ec2_instances_max_start_time: EnvVarsDict,
    minimal_configuration: None,
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    create_services_batch: Callable[[_ScaleUpParams], Awaitable[list[Service]]],
    ec2_client: EC2Client,
    mock_find_node_with_name_returns_none: mock.Mock,
    mock_docker_tag_node: mock.Mock,
    mock_rabbitmq_post_message: mock.Mock,
    short_ec2_instance_max_start_time: datetime.timedelta,
    ec2_instance_custom_tags: dict[str, str],
    instance_type_filters: Sequence[FilterTypeDef],
    scale_up_params: _ScaleUpParams,
):
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    assert (
        short_ec2_instance_max_start_time
        == app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_START_TIME
    )
    # we have nothing running now
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]
    await create_services_batch(scale_up_params)

    # this should trigger a scaling up as we have no nodes
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )

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
    mock_find_node_with_name_returns_none.assert_not_called()
    mock_docker_tag_node.assert_not_called()
    # check rabbit messages were sent
    _assert_rabbit_autoscaling_message_sent(
        mock_rabbitmq_post_message,
        app_settings,
        initialized_app,
        instances_running=0,
        instances_pending=scale_up_params.expected_num_instances,
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
            expected_num_instances=scale_up_params.expected_num_instances,
            expected_instance_type=scale_up_params.expected_instance_type,
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
            instances_pending=scale_up_params.expected_num_instances,
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
    assert (
        len(all_instances["Reservations"][0]["Instances"])
        == scale_up_params.expected_num_instances
    )
    assert "State" in all_instances["Reservations"][0]["Instances"][0]
    assert "Name" in all_instances["Reservations"][0]["Instances"][0]["State"]
    assert (
        all_instances["Reservations"][0]["Instances"][0]["State"]["Name"]
        == "terminated"
    )

    assert "Instances" in all_instances["Reservations"][1]
    assert (
        len(all_instances["Reservations"][1]["Instances"])
        == scale_up_params.expected_num_instances
    )
    assert "State" in all_instances["Reservations"][1]["Instances"][0]
    assert "Name" in all_instances["Reservations"][1]["Instances"][0]["State"]
    assert (
        all_instances["Reservations"][1]["Instances"][0]["State"]["Name"] == "running"
    )


@pytest.mark.parametrize(
    # NOTE: only the main test test_cluster_scaling_up_and_down is run with all options
    "with_docker_join_drained",
    ["without_AUTOSCALING_DOCKER_JOIN_DRAINED"],
    indirect=True,
)
@pytest.mark.parametrize(
    # NOTE: only the main test test_cluster_scaling_up_and_down is run with all options
    "with_drain_nodes_labelled",
    ["with_AUTOSCALING_DRAIN_NODES_WITH_LABELS"],
    indirect=True,
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
        buffer_drained_nodes=[
            AssociatedInstance(node=host_node, ec2_instance=fake_ec2_instance_data())
        ],
    )
    assert await _find_terminateable_instances(initialized_app, active_cluster) == []


@pytest.mark.parametrize(
    # NOTE: only the main test test_cluster_scaling_up_and_down is run with all options
    "with_docker_join_drained",
    ["without_AUTOSCALING_DOCKER_JOIN_DRAINED"],
    indirect=True,
)
@pytest.mark.parametrize(
    # NOTE: only the main test test_cluster_scaling_up_and_down is run with all options
    "with_drain_nodes_labelled",
    ["with_AUTOSCALING_DRAIN_NODES_WITH_LABELS"],
    indirect=True,
)
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
        buffer_drained_nodes=[
            create_associated_instance(drained_host_node, True)  # noqa: FBT003
        ],
    )
    updated_cluster = await _try_scale_down_cluster(initialized_app, active_cluster)
    assert updated_cluster == active_cluster
    mock_remove_nodes.assert_not_called()


@pytest.mark.parametrize(
    # NOTE: only the main test test_cluster_scaling_up_and_down is run with all options
    "with_docker_join_drained",
    ["without_AUTOSCALING_DOCKER_JOIN_DRAINED"],
    indirect=True,
)
@pytest.mark.parametrize(
    # NOTE: only the main test test_cluster_scaling_up_and_down is run with all options
    "with_drain_nodes_labelled",
    ["with_AUTOSCALING_DRAIN_NODES_WITH_LABELS"],
    indirect=True,
)
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
    updated_cluster = await _activate_drained_nodes(initialized_app, empty_cluster)
    assert updated_cluster == empty_cluster

    active_cluster = cluster(
        active_nodes=[create_associated_instance(host_node, True)],  # noqa: FBT003
        drained_nodes=[
            create_associated_instance(drained_host_node, True)  # noqa: FBT003
        ],
        buffer_drained_nodes=[
            create_associated_instance(drained_host_node, True)  # noqa: FBT003
        ],
    )
    updated_cluster = await _activate_drained_nodes(initialized_app, active_cluster)
    assert updated_cluster == active_cluster
    mock_docker_tag_node.assert_not_called()


@pytest.mark.parametrize(
    # NOTE: only the main test test_cluster_scaling_up_and_down is run with all options
    "with_docker_join_drained",
    ["without_AUTOSCALING_DOCKER_JOIN_DRAINED"],
    indirect=True,
)
@pytest.mark.parametrize(
    # NOTE: only the main test test_cluster_scaling_up_and_down is run with all options
    "with_drain_nodes_labelled",
    ["with_AUTOSCALING_DRAIN_NODES_WITH_LABELS"],
    indirect=True,
)
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
    assert service_with_no_reservations.spec
    service_tasks = TypeAdapter(list[Task]).validate_python(
        await autoscaling_docker.tasks.list(
            filters={"service": service_with_no_reservations.spec.name}
        )
    )
    assert service_tasks
    assert len(service_tasks) == 1

    cluster_without_drained_nodes = cluster(
        active_nodes=[create_associated_instance(host_node, True)]  # noqa: FBT003
    )
    updated_cluster = await _activate_drained_nodes(
        initialized_app, cluster_without_drained_nodes
    )
    assert updated_cluster == cluster_without_drained_nodes
    mock_docker_tag_node.assert_not_called()


@pytest.mark.parametrize(
    # NOTE: only the main test test_cluster_scaling_up_and_down is run with all options
    "with_docker_join_drained",
    ["without_AUTOSCALING_DOCKER_JOIN_DRAINED"],
    indirect=True,
)
@pytest.mark.parametrize(
    # NOTE: only the main test test_cluster_scaling_up_and_down is run with all options
    "with_drain_nodes_labelled",
    ["with_AUTOSCALING_DRAIN_NODES_WITH_LABELS"],
    indirect=True,
)
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
    assert service_with_no_reservations.spec
    service_tasks = TypeAdapter(list[Task]).validate_python(
        await autoscaling_docker.tasks.list(
            filters={"service": service_with_no_reservations.spec.name}
        )
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
        initialized_app, cluster_with_drained_nodes
    )
    # they are the same nodes, but the availability might have changed here
    assert updated_cluster.active_nodes != cluster_with_drained_nodes.drained_nodes
    assert (
        updated_cluster.active_nodes[0].assigned_tasks
        == cluster_with_drained_nodes.drained_nodes[0].assigned_tasks
    )
    assert (
        updated_cluster.active_nodes[0].ec2_instance
        == cluster_with_drained_nodes.drained_nodes[0].ec2_instance
    )

    assert drained_host_node.spec
    mock_docker_tag_node.assert_called_once_with(
        mock.ANY,
        drained_host_node,
        tags={
            _OSPARC_SERVICE_READY_LABEL_KEY: "true",
            _OSPARC_SERVICES_READY_DATETIME_LABEL_KEY: mock.ANY,
        },
        available=True,
    )


@pytest.mark.parametrize(
    # NOTE: only the main test test_cluster_scaling_up_and_down is run with all options
    "with_docker_join_drained",
    ["without_AUTOSCALING_DOCKER_JOIN_DRAINED"],
    indirect=True,
)
@pytest.mark.parametrize(
    # NOTE: only the main test test_cluster_scaling_up_and_down is run with all options
    "with_drain_nodes_labelled",
    ["with_AUTOSCALING_DRAIN_NODES_WITH_LABELS"],
    indirect=True,
)
async def test_warm_buffers_are_started_to_replace_missing_hot_buffers(
    patch_ec2_client_launch_instances_min_number_of_instances: mock.Mock,
    minimal_configuration: None,
    with_instances_machines_hot_buffer: EnvVarsDict,
    ec2_client: EC2Client,
    initialized_app: FastAPI,
    app_settings: ApplicationSettings,
    ec2_instance_custom_tags: dict[str, str],
    buffer_count: int,
    create_buffer_machines: Callable[
        [int, InstanceTypeType, InstanceStateNameType, list[DockerGenericTag] | None],
        Awaitable[list[str]],
    ],
    spied_cluster_analysis: MockType,
    instance_type_filters: Sequence[FilterTypeDef],
    mock_find_node_with_name_returns_fake_node: mock.Mock,
    mock_compute_node_used_resources: mock.Mock,
    mock_docker_tag_node: mock.Mock,
):
    # pre-requisites
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    assert app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER > 0

    # we have nothing running now
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]

    # have a few warm buffers ready with the same type as the hot buffer machines
    buffer_machines = await create_buffer_machines(
        buffer_count,
        cast(
            InstanceTypeType,
            next(
                iter(app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES)
            ),
        ),
        "stopped",
        None,
    )
    await assert_autoscaled_dynamic_warm_pools_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=buffer_count,
        expected_instance_type=cast(
            InstanceTypeType,
            next(
                iter(app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES)
            ),
        ),
        expected_instance_state="stopped",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
        expected_pre_pulled_images=None,
        instance_filters=None,
    )

    # let's autoscale, this should move the warm buffers to hot buffers
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )
    mock_docker_tag_node.assert_not_called()
    # at analysis time, we had no machines running
    analyzed_cluster = assert_cluster_state(
        spied_cluster_analysis,
        expected_calls=1,
        expected_num_machines=0,
    )
    assert not analyzed_cluster.active_nodes
    assert analyzed_cluster.buffer_ec2s
    assert len(analyzed_cluster.buffer_ec2s) == len(buffer_machines)

    # now we should have a warm buffer moved to the hot buffer
    await assert_autoscaled_dynamic_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER,
        expected_instance_type=cast(
            InstanceTypeType,
            next(
                iter(app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES)
            ),
        ),
        expected_instance_state="running",
        expected_additional_tag_keys=[
            *list(ec2_instance_custom_tags),
            BUFFER_MACHINE_TAG_KEY,
        ],
        instance_filters=instance_type_filters,
        expected_user_data=[],
    )

    # let's autoscale again, to check the cluster analysis and tag the nodes
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )
    mock_docker_tag_node.assert_called()
    assert (
        mock_docker_tag_node.call_count
        == app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER
    )
    # at analysis time, we had no machines running
    analyzed_cluster = assert_cluster_state(
        spied_cluster_analysis,
        expected_calls=1,
        expected_num_machines=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER,
    )
    assert not analyzed_cluster.active_nodes
    assert len(analyzed_cluster.buffer_ec2s) == max(
        0,
        buffer_count
        - app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER,
    ), (
        "the warm buffers were not used as expected there should be"
        f" {buffer_count - app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER} remaining, "
        f"found {len(analyzed_cluster.buffer_ec2s)}"
    )
    assert (
        len(analyzed_cluster.pending_ec2s)
        == app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER
    )


@pytest.mark.parametrize(
    # NOTE: only the main test test_cluster_scaling_up_and_down is run with all options
    "with_docker_join_drained",
    ["without_AUTOSCALING_DOCKER_JOIN_DRAINED"],
    indirect=True,
)
@pytest.mark.parametrize(
    # NOTE: only the main test test_cluster_scaling_up_and_down is run with all options
    "with_drain_nodes_labelled",
    ["with_AUTOSCALING_DRAIN_NODES_WITH_LABELS"],
    indirect=True,
)
async def test_warm_buffers_only_replace_hot_buffer_if_service_is_started_issue7071(
    patch_ec2_client_launch_instances_min_number_of_instances: mock.Mock,
    minimal_configuration: None,
    with_instances_machines_hot_buffer: EnvVarsDict,
    with_drain_nodes_labelled: bool,
    ec2_client: EC2Client,
    initialized_app: FastAPI,
    app_settings: ApplicationSettings,
    ec2_instance_custom_tags: dict[str, str],
    buffer_count: int,
    create_buffer_machines: Callable[
        [int, InstanceTypeType, InstanceStateNameType, list[DockerGenericTag] | None],
        Awaitable[list[str]],
    ],
    create_services_batch: Callable[[_ScaleUpParams], Awaitable[list[Service]]],
    hot_buffer_instance_type: InstanceTypeType,
    spied_cluster_analysis: MockType,
    instance_type_filters: Sequence[FilterTypeDef],
    stopped_instance_type_filters: Sequence[FilterTypeDef],
    mock_find_node_with_name_returns_fake_node: mock.Mock,
    mock_compute_node_used_resources: mock.Mock,
    mock_docker_tag_node: mock.Mock,
    mocker: MockerFixture,
    fake_node: Node,
):
    # NOTE: https://github.com/ITISFoundation/osparc-simcore/issues/7071

    #
    # PRE-requisites
    #
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    assert app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER > 0
    num_hot_buffer = (
        app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER
    )

    # we have nothing running now
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]

    # ensure we get our running hot buffer
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )
    await assert_autoscaled_dynamic_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=num_hot_buffer,
        expected_instance_type=hot_buffer_instance_type,
        expected_instance_state="running",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
        instance_filters=instance_type_filters,
    )
    # this brings a new analysis
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )
    spied_cluster = assert_cluster_state(
        spied_cluster_analysis, expected_calls=2, expected_num_machines=5
    )
    # calling again should attach the new nodes to the reserve, but nothing should start
    fake_attached_node_base = deepcopy(fake_node)
    assert fake_attached_node_base.spec
    fake_attached_node_base.spec.availability = (
        Availability.active if with_drain_nodes_labelled else Availability.drain
    )
    assert fake_attached_node_base.spec.labels
    assert app_settings.AUTOSCALING_NODES_MONITORING
    expected_docker_node_tags = dict.fromkeys(
        app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS
        + app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NEW_NODES_LABELS,
        "true",
    ) | {
        DOCKER_TASK_EC2_INSTANCE_TYPE_PLACEMENT_CONSTRAINT_KEY: f"{hot_buffer_instance_type}"
    }
    fake_attached_node_base.spec.labels |= expected_docker_node_tags | {
        _OSPARC_SERVICE_READY_LABEL_KEY: "false"
    }
    assert fake_attached_node_base.status
    fake_attached_node_base.status.state = NodeState.ready
    fake_hot_buffer_nodes = []
    for i in range(num_hot_buffer):
        node = fake_attached_node_base.model_copy(deep=True)
        assert node.description
        node.description.hostname = node_host_name_from_ec2_private_dns(
            spied_cluster.pending_ec2s[i].ec2_instance
        )
        fake_hot_buffer_nodes.append(node)
    auto_scaling_mode = DynamicAutoscaling()
    mocker.patch.object(
        auto_scaling_mode,
        "get_monitored_nodes",
        autospec=True,
        return_value=fake_hot_buffer_nodes,
    )

    await auto_scale_cluster(app=initialized_app, auto_scaling_mode=auto_scaling_mode)
    await assert_autoscaled_dynamic_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=num_hot_buffer,
        expected_instance_type=hot_buffer_instance_type,
        expected_instance_state="running",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
        instance_filters=instance_type_filters,
    )
    spied_cluster = assert_cluster_state(
        spied_cluster_analysis, expected_calls=1, expected_num_machines=5
    )
    assert len(spied_cluster.buffer_drained_nodes) == num_hot_buffer
    assert not spied_cluster.buffer_ec2s

    # have a few warm buffers ready with the same type as the hot buffer machines
    await create_buffer_machines(
        buffer_count,
        hot_buffer_instance_type,
        "stopped",
        None,
    )
    await assert_autoscaled_dynamic_warm_pools_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=buffer_count,
        expected_instance_type=hot_buffer_instance_type,
        expected_instance_state="stopped",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
        expected_pre_pulled_images=None,
        instance_filters=stopped_instance_type_filters,
    )

    # calling again should do nothing
    await auto_scale_cluster(app=initialized_app, auto_scaling_mode=auto_scaling_mode)
    await assert_autoscaled_dynamic_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=num_hot_buffer,
        expected_instance_type=hot_buffer_instance_type,
        expected_instance_state="running",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
        instance_filters=instance_type_filters,
    )
    await assert_autoscaled_dynamic_warm_pools_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=buffer_count,
        expected_instance_type=hot_buffer_instance_type,
        expected_instance_state="stopped",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
        expected_pre_pulled_images=None,
        instance_filters=stopped_instance_type_filters,
    )
    spied_cluster = assert_cluster_state(
        spied_cluster_analysis, expected_calls=1, expected_num_machines=5
    )
    assert len(spied_cluster.buffer_drained_nodes) == num_hot_buffer
    assert len(spied_cluster.buffer_ec2s) == buffer_count

    #
    # BUG REPRODUCTION
    #
    # start a service that imposes same type as the hot buffer
    assert hot_buffer_instance_type == "t2.xlarge", (
        "the test is hard-coded for this type and accordingly resource. If this changed then the resource shall be changed too"
    )
    scale_up_params = _ScaleUpParams(
        imposed_instance_type=hot_buffer_instance_type,
        service_resources=Resources(
            cpus=2, ram=TypeAdapter(ByteSize).validate_python("1Gib")
        ),
        num_services=1,
        expected_instance_type="t2.xlarge",
        expected_num_instances=1,
    )
    await create_services_batch(scale_up_params)

    # this should trigger usage of the hot buffer and the warm buffers should replace the hot buffer
    await auto_scale_cluster(app=initialized_app, auto_scaling_mode=auto_scaling_mode)
    await assert_autoscaled_dynamic_ec2_instances(
        ec2_client,
        expected_num_reservations=2,
        check_reservation_index=0,
        expected_num_instances=num_hot_buffer,
        expected_instance_type=hot_buffer_instance_type,
        expected_instance_state="running",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
        instance_filters=instance_type_filters,
    )
    await assert_autoscaled_dynamic_warm_pools_ec2_instances(
        ec2_client,
        expected_num_reservations=2,
        check_reservation_index=1,
        expected_num_instances=1,
        expected_instance_type=hot_buffer_instance_type,
        expected_instance_state="running",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
        expected_pre_pulled_images=None,
        instance_filters=instance_type_filters,
    )
    await assert_autoscaled_dynamic_warm_pools_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=buffer_count - 1,
        expected_instance_type=hot_buffer_instance_type,
        expected_instance_state="stopped",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
        expected_pre_pulled_images=None,
        instance_filters=stopped_instance_type_filters,
    )
    # simulate one of the hot buffer is not drained anymore and took the pending service
    random_fake_node = random.choice(fake_hot_buffer_nodes)  # noqa: S311
    random_fake_node.spec.labels[_OSPARC_SERVICE_READY_LABEL_KEY] = "true"
    random_fake_node.spec.labels[_OSPARC_SERVICES_READY_DATETIME_LABEL_KEY] = (
        arrow.utcnow().isoformat()
    )
    random_fake_node.spec.availability = Availability.active
    # simulate the fact that the warm buffer that just started is not yet visible
    mock_find_node_with_name_returns_fake_node.return_value = None

    # get the new analysis
    await auto_scale_cluster(app=initialized_app, auto_scaling_mode=auto_scaling_mode)
    spied_cluster = assert_cluster_state(
        spied_cluster_analysis, expected_calls=2, expected_num_machines=6
    )
    assert len(spied_cluster.buffer_drained_nodes) == num_hot_buffer - 1
    assert len(spied_cluster.buffer_ec2s) == buffer_count - 1
    assert len(spied_cluster.active_nodes) == 1
    assert len(spied_cluster.pending_ec2s) == 1

    # running it again shall do nothing
    @tenacity.retry(
        retry=tenacity.retry_always,
        reraise=True,
        wait=tenacity.wait_fixed(0.1),
        stop=tenacity.stop_after_attempt(10),
    )
    async def _check_autoscaling_is_stable() -> None:
        await auto_scale_cluster(
            app=initialized_app, auto_scaling_mode=auto_scaling_mode
        )
        spied_cluster = assert_cluster_state(
            spied_cluster_analysis, expected_calls=1, expected_num_machines=6
        )
        assert len(spied_cluster.buffer_drained_nodes) == num_hot_buffer - 1
        assert len(spied_cluster.buffer_ec2s) == buffer_count - 1
        assert len(spied_cluster.active_nodes) == 1
        assert len(spied_cluster.pending_ec2s) == 1

    with pytest.raises(tenacity.RetryError):
        await _check_autoscaling_is_stable()
