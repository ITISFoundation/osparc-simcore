# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements


import asyncio
import datetime
import logging
from collections import defaultdict
from collections.abc import Callable, Iterator
from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from unittest import mock

import arrow
import distributed
import pytest
from aws_library.ec2 import Resources
from dask_task_models_library.resource_constraints import (
    create_ec2_resource_constraint_key,
)
from faker import Faker
from fastapi import FastAPI
from models_library.docker import DOCKER_TASK_EC2_INSTANCE_TYPE_PLACEMENT_CONSTRAINT_KEY
from models_library.generated_models.docker_rest_api import Availability
from models_library.generated_models.docker_rest_api import Node as DockerNode
from models_library.generated_models.docker_rest_api import NodeState, NodeStatus
from models_library.rabbitmq_messages import RabbitAutoscalingStatusMessage
from pydantic import ByteSize, parse_obj_as
from pytest_mock import MockerFixture
from pytest_simcore.helpers.aws_ec2 import assert_autoscaled_computational_ec2_instances
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from simcore_service_autoscaling.core.settings import ApplicationSettings
from simcore_service_autoscaling.models import EC2InstanceData
from simcore_service_autoscaling.modules.auto_scaling_core import auto_scale_cluster
from simcore_service_autoscaling.modules.auto_scaling_mode_computational import (
    ComputationalAutoscaling,
)
from simcore_service_autoscaling.modules.dask import DaskTaskResources
from simcore_service_autoscaling.modules.docker import get_docker_client
from simcore_service_autoscaling.modules.ec2 import SimcoreEC2API
from simcore_service_autoscaling.utils.utils_docker import (
    _OSPARC_NODE_EMPTY_DATETIME_LABEL_KEY,
    _OSPARC_NODE_TERMINATION_PROCESS_LABEL_KEY,
    _OSPARC_SERVICE_READY_LABEL_KEY,
    _OSPARC_SERVICES_READY_DATETIME_LABEL_KEY,
)
from types_aiobotocore_ec2.client import EC2Client
from types_aiobotocore_ec2.literals import InstanceTypeType


@pytest.fixture
def local_dask_scheduler_server_envs(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    dask_spec_local_cluster: distributed.SpecCluster,
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "DASK_MONITORING_URL": dask_spec_local_cluster.scheduler_address,
        },
    )


@pytest.fixture
def minimal_configuration(
    with_labelize_drain_nodes: EnvVarsDict,
    docker_swarm: None,
    mocked_ec2_server_envs: EnvVarsDict,
    mocked_ssm_server_envs: EnvVarsDict,
    enabled_computational_mode: EnvVarsDict,
    local_dask_scheduler_server_envs: EnvVarsDict,
    mocked_ec2_instances_envs: EnvVarsDict,
    disabled_rabbitmq: None,
    disable_dynamic_service_background_task: None,
    disable_buffers_pool_background_task: None,
    mocked_redis_server: None,
) -> None:
    ...


@pytest.fixture
def dask_workers_config() -> dict[str, Any]:
    # NOTE: we override here the config to get a "weak" cluster
    return {
        "weak-worker": {
            "cls": distributed.Worker,
            "options": {"nthreads": 2, "resources": {"CPU": 2, "RAM": 2e9}},
        }
    }


def _assert_rabbit_autoscaling_message_sent(
    mock_rabbitmq_post_message: mock.Mock,
    app_settings: ApplicationSettings,
    app: FastAPI,
    scheduler_address: str,
    **message_update_kwargs,
):
    default_message = RabbitAutoscalingStatusMessage(
        origin=f"computational:scheduler_url={scheduler_address}",
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


@pytest.fixture
def mock_docker_find_node_with_name_returns_fake_node(
    mocker: MockerFixture, fake_node: DockerNode
) -> Iterator[mock.Mock]:
    return mocker.patch(
        "simcore_service_autoscaling.modules.auto_scaling_core.utils_docker.find_node_with_name",
        autospec=True,
        return_value=fake_node,
    )


@pytest.fixture
def mock_docker_compute_node_used_resources(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "simcore_service_autoscaling.modules.auto_scaling_core.utils_docker.compute_node_used_resources",
        autospec=True,
        return_value=Resources.create_as_empty(),
    )


@pytest.fixture
def mock_rabbitmq_post_message(mocker: MockerFixture) -> Iterator[mock.Mock]:
    return mocker.patch(
        "simcore_service_autoscaling.utils.rabbitmq.post_message", autospec=True
    )


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
def ec2_instance_custom_tags(
    ec2_instance_custom_tags: dict[str, str],
    faker: Faker,
) -> dict[str, str]:
    # NOTE: we override here the config as the autoscaling in computational case is started with more custom tags
    return {
        **ec2_instance_custom_tags,
        "user_id": faker.word(),
        "wallet_id": faker.word(),
    }


async def test_cluster_scaling_with_no_tasks_does_nothing(
    minimal_configuration: None,
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    mock_launch_instances: mock.Mock,
    mock_terminate_instances: mock.Mock,
    mock_rabbitmq_post_message: mock.Mock,
    dask_spec_local_cluster: distributed.SpecCluster,
):
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=ComputationalAutoscaling()
    )
    mock_launch_instances.assert_not_called()
    mock_terminate_instances.assert_not_called()
    _assert_rabbit_autoscaling_message_sent(
        mock_rabbitmq_post_message,
        app_settings,
        initialized_app,
        dask_spec_local_cluster.scheduler_address,
    )


@pytest.mark.acceptance_test(
    "Ensure this does not happen https://github.com/ITISFoundation/osparc-simcore/issues/6227"
)
async def test_cluster_scaling_with_disabled_ssm_does_not_block_autoscaling(
    minimal_configuration: None,
    disabled_ssm: None,
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    mock_launch_instances: mock.Mock,
    mock_terminate_instances: mock.Mock,
    mock_rabbitmq_post_message: mock.Mock,
    dask_spec_local_cluster: distributed.SpecCluster,
):
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=ComputationalAutoscaling()
    )
    mock_launch_instances.assert_not_called()
    mock_terminate_instances.assert_not_called()
    _assert_rabbit_autoscaling_message_sent(
        mock_rabbitmq_post_message,
        app_settings,
        initialized_app,
        dask_spec_local_cluster.scheduler_address,
    )


async def test_cluster_scaling_with_task_with_too_much_resources_starts_nothing(
    minimal_configuration: None,
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    create_dask_task: Callable[[DaskTaskResources], distributed.Future],
    mock_launch_instances: mock.Mock,
    mock_terminate_instances: mock.Mock,
    mock_rabbitmq_post_message: mock.Mock,
    dask_spec_local_cluster: distributed.SpecCluster,
):
    # create a task that needs too much power
    dask_future = create_dask_task({"RAM": int(parse_obj_as(ByteSize, "12800GiB"))})
    assert dask_future

    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=ComputationalAutoscaling()
    )
    mock_launch_instances.assert_not_called()
    mock_terminate_instances.assert_not_called()
    _assert_rabbit_autoscaling_message_sent(
        mock_rabbitmq_post_message,
        app_settings,
        initialized_app,
        dask_spec_local_cluster.scheduler_address,
    )


@pytest.fixture
def create_dask_task_resources() -> Callable[..., DaskTaskResources]:
    def _do(
        ec2_instance_type: InstanceTypeType | None, ram: ByteSize
    ) -> DaskTaskResources:
        resources = DaskTaskResources(
            {
                "RAM": int(ram),
            }
        )
        if ec2_instance_type is not None:
            resources[create_ec2_resource_constraint_key(ec2_instance_type)] = 1
        return resources

    return _do


@pytest.fixture
def mock_dask_get_worker_has_results_in_memory(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "simcore_service_autoscaling.modules.dask.get_worker_still_has_results_in_memory",
        return_value=0,
        autospec=True,
    )


@pytest.fixture
def mock_dask_get_worker_used_resources(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "simcore_service_autoscaling.modules.dask.get_worker_used_resources",
        return_value=Resources.create_as_empty(),
        autospec=True,
    )


@pytest.fixture
def mock_dask_is_worker_connected(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "simcore_service_autoscaling.modules.dask.is_worker_connected",
        return_value=True,
        autospec=True,
    )


async def _create_task_with_resources(
    ec2_client: EC2Client,
    dask_task_imposed_ec2_type: InstanceTypeType | None,
    dask_ram: ByteSize | None,
    create_dask_task_resources: Callable[..., DaskTaskResources],
    create_dask_task: Callable[[DaskTaskResources], distributed.Future],
) -> distributed.Future:
    if dask_task_imposed_ec2_type and not dask_ram:
        instance_types = await ec2_client.describe_instance_types(
            InstanceTypes=[dask_task_imposed_ec2_type]
        )
        assert instance_types
        assert "InstanceTypes" in instance_types
        assert instance_types["InstanceTypes"]
        assert "MemoryInfo" in instance_types["InstanceTypes"][0]
        assert "SizeInMiB" in instance_types["InstanceTypes"][0]["MemoryInfo"]
        dask_ram = parse_obj_as(
            ByteSize,
            f"{instance_types['InstanceTypes'][0]['MemoryInfo']['SizeInMiB']}MiB",
        )
    dask_task_resources = create_dask_task_resources(
        dask_task_imposed_ec2_type, dask_ram
    )
    dask_future = create_dask_task(dask_task_resources)
    assert dask_future
    return dask_future


@pytest.mark.acceptance_test()
@pytest.mark.parametrize(
    "dask_task_imposed_ec2_type, dask_ram, expected_ec2_type",
    [
        pytest.param(
            None,
            parse_obj_as(ByteSize, "128Gib"),
            "r5n.4xlarge",
            id="No explicit instance defined",
        ),
        pytest.param(
            "g4dn.2xlarge",
            None,
            "g4dn.2xlarge",
            id="Explicitely ask for g4dn.2xlarge and use all the resources",
        ),
        pytest.param(
            "r5n.8xlarge",
            parse_obj_as(ByteSize, "116Gib"),
            "r5n.8xlarge",
            id="Explicitely ask for r5n.8xlarge and set the resources",
        ),
        pytest.param(
            "r5n.8xlarge",
            None,
            "r5n.8xlarge",
            id="Explicitely ask for r5n.8xlarge and use all the resources",
        ),
    ],
)
async def test_cluster_scaling_up_and_down(  # noqa: PLR0915
    minimal_configuration: None,
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    create_dask_task: Callable[[DaskTaskResources], distributed.Future],
    ec2_client: EC2Client,
    mock_docker_tag_node: mock.Mock,
    fake_node: DockerNode,
    mock_rabbitmq_post_message: mock.Mock,
    mock_docker_find_node_with_name_returns_fake_node: mock.Mock,
    mock_docker_set_node_availability: mock.Mock,
    mock_docker_compute_node_used_resources: mock.Mock,
    mock_dask_get_worker_has_results_in_memory: mock.Mock,
    mock_dask_get_worker_used_resources: mock.Mock,
    mock_dask_is_worker_connected: mock.Mock,
    mocker: MockerFixture,
    dask_spec_local_cluster: distributed.SpecCluster,
    create_dask_task_resources: Callable[..., DaskTaskResources],
    dask_task_imposed_ec2_type: InstanceTypeType | None,
    dask_ram: ByteSize | None,
    expected_ec2_type: InstanceTypeType,
    with_drain_nodes_labelled: bool,
    ec2_instance_custom_tags: dict[str, str],
):
    # we have nothing running now
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]

    # create a task that needs more power
    dask_future = await _create_task_with_resources(
        ec2_client,
        dask_task_imposed_ec2_type,
        dask_ram,
        create_dask_task_resources,
        create_dask_task,
    )

    # this should trigger a scaling up as we have no nodes
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=ComputationalAutoscaling()
    )

    # check the instance was started and we have exactly 1
    await assert_autoscaled_computational_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=1,
        expected_instance_type=expected_ec2_type,
        expected_instance_state="running",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
    )

    # as the new node is already running, but is not yet connected, hence not tagged and drained
    mock_docker_find_node_with_name_returns_fake_node.assert_not_called()
    mock_docker_tag_node.assert_not_called()
    mock_docker_set_node_availability.assert_not_called()
    mock_docker_compute_node_used_resources.assert_not_called()
    mock_dask_get_worker_has_results_in_memory.assert_not_called()
    mock_dask_get_worker_used_resources.assert_not_called()
    mock_dask_is_worker_connected.assert_not_called()
    # check rabbit messages were sent
    _assert_rabbit_autoscaling_message_sent(
        mock_rabbitmq_post_message,
        app_settings,
        initialized_app,
        dask_spec_local_cluster.scheduler_address,
        instances_running=0,
        instances_pending=1,
    )
    mock_rabbitmq_post_message.reset_mock()

    # 2. running this again should not scale again, but tag the node and make it available
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=ComputationalAutoscaling()
    )
    mock_dask_get_worker_has_results_in_memory.assert_called_once()
    mock_dask_get_worker_has_results_in_memory.reset_mock()
    mock_dask_get_worker_used_resources.assert_called_once()
    mock_dask_get_worker_used_resources.reset_mock()
    mock_dask_is_worker_connected.assert_not_called()
    instances = await assert_autoscaled_computational_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=1,
        expected_instance_type=expected_ec2_type,
        expected_instance_state="running",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
    )
    assert len(instances) == 1
    assert "PrivateDnsName" in instances[0]
    internal_dns_name = instances[0]["PrivateDnsName"].removesuffix(".ec2.internal")

    # the node is attached first and then tagged and made active right away since we still have the pending task
    mock_docker_find_node_with_name_returns_fake_node.assert_called_once()
    mock_docker_find_node_with_name_returns_fake_node.reset_mock()
    expected_docker_node_tags = {
        DOCKER_TASK_EC2_INSTANCE_TYPE_PLACEMENT_CONSTRAINT_KEY: expected_ec2_type
    }
    assert mock_docker_tag_node.call_count == 2
    assert fake_node.Spec
    assert fake_node.Spec.Labels
    fake_attached_node = deepcopy(fake_node)
    assert fake_attached_node.Spec
    fake_attached_node.Spec.Availability = (
        Availability.active if with_drain_nodes_labelled else Availability.drain
    )
    assert fake_attached_node.Spec.Labels
    fake_attached_node.Spec.Labels |= expected_docker_node_tags | {
        _OSPARC_SERVICE_READY_LABEL_KEY: "false",
    }
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
    mock_rabbitmq_post_message.assert_called_once()
    mock_rabbitmq_post_message.reset_mock()

    # now we have 1 monitored node that needs to be mocked
    fake_attached_node.Spec.Labels[_OSPARC_SERVICE_READY_LABEL_KEY] = "true"
    fake_attached_node.Status = NodeStatus(
        State=NodeState.ready, Message=None, Addr=None
    )
    fake_attached_node.Spec.Availability = Availability.active
    assert fake_attached_node.Description
    fake_attached_node.Description.Hostname = internal_dns_name

    auto_scaling_mode = ComputationalAutoscaling()
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
    mock_dask_is_worker_connected.assert_called()
    assert mock_dask_is_worker_connected.call_count == num_useless_calls
    mock_dask_is_worker_connected.reset_mock()
    mock_dask_get_worker_has_results_in_memory.assert_called()
    assert (
        mock_dask_get_worker_has_results_in_memory.call_count == 2 * num_useless_calls
    )
    mock_dask_get_worker_has_results_in_memory.reset_mock()
    mock_dask_get_worker_used_resources.assert_called()
    assert mock_dask_get_worker_used_resources.call_count == 2 * num_useless_calls
    mock_dask_get_worker_used_resources.reset_mock()
    mock_docker_find_node_with_name_returns_fake_node.assert_not_called()
    mock_docker_tag_node.assert_not_called()
    mock_docker_set_node_availability.assert_not_called()
    # check the number of instances did not change and is still running
    await assert_autoscaled_computational_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=1,
        expected_instance_type=expected_ec2_type,
        expected_instance_state="running",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
    )

    # check rabbit messages were sent
    mock_rabbitmq_post_message.assert_called()
    assert mock_rabbitmq_post_message.call_count == num_useless_calls
    mock_rabbitmq_post_message.reset_mock()

    #
    # 4. now scaling down, as we deleted all the tasks
    #
    del dask_future
    await auto_scale_cluster(app=initialized_app, auto_scaling_mode=auto_scaling_mode)
    mock_dask_is_worker_connected.assert_called_once()
    mock_dask_is_worker_connected.reset_mock()
    mock_dask_get_worker_has_results_in_memory.assert_called()
    assert mock_dask_get_worker_has_results_in_memory.call_count == 2
    mock_dask_get_worker_has_results_in_memory.reset_mock()
    mock_dask_get_worker_used_resources.assert_called()
    assert mock_dask_get_worker_used_resources.call_count == 2
    mock_dask_get_worker_used_resources.reset_mock()
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
    mock_dask_is_worker_connected.assert_called_once()
    mock_dask_is_worker_connected.reset_mock()
    mock_dask_get_worker_has_results_in_memory.assert_called()
    assert mock_dask_get_worker_has_results_in_memory.call_count == 2
    mock_dask_get_worker_has_results_in_memory.reset_mock()
    mock_dask_get_worker_used_resources.assert_called()
    assert mock_dask_get_worker_used_resources.call_count == 2
    mock_dask_get_worker_used_resources.reset_mock()
    # the node shall be set to drain, but not yet terminated
    mock_docker_set_node_availability.assert_not_called()
    mock_docker_tag_node.assert_called_once_with(
        get_docker_client(initialized_app),
        fake_attached_node,
        tags=fake_attached_node.Spec.Labels
        | {
            _OSPARC_NODE_EMPTY_DATETIME_LABEL_KEY: mock.ANY,
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

    await assert_autoscaled_computational_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=1,
        expected_instance_type=expected_ec2_type,
        expected_instance_state="running",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
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
    await assert_autoscaled_computational_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=1,
        expected_instance_type=expected_ec2_type,
        expected_instance_state="running",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
    )

    # now changing the last update timepoint will trigger the node removal and shutdown the ec2 instance
    fake_attached_node.Spec.Labels[_OSPARC_SERVICES_READY_DATETIME_LABEL_KEY] = (
        datetime.datetime.now(tz=datetime.timezone.utc)
        - app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
        - datetime.timedelta(seconds=1)
    ).isoformat()
    # first making sure the node is drained, then terminate it after a delay to let it drain
    await auto_scale_cluster(app=initialized_app, auto_scaling_mode=auto_scaling_mode)
    mocked_docker_remove_node.assert_not_called()
    await assert_autoscaled_computational_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=1,
        expected_instance_type=expected_ec2_type,
        expected_instance_state="running",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
    )
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
    await assert_autoscaled_computational_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=1,
        expected_instance_type=expected_ec2_type,
        expected_instance_state="terminated",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
    )

    # this call should never be used in computational mode
    mock_docker_compute_node_used_resources.assert_not_called()


async def test_cluster_does_not_scale_up_if_defined_instance_is_not_allowed(
    minimal_configuration: None,
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    create_dask_task: Callable[[DaskTaskResources], distributed.Future],
    create_dask_task_resources: Callable[..., DaskTaskResources],
    ec2_client: EC2Client,
    faker: Faker,
    caplog: pytest.LogCaptureFixture,
):
    # we have nothing running now
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]

    # create a task that needs more power
    dask_task_resources = create_dask_task_resources(
        faker.pystr(), parse_obj_as(ByteSize, "128GiB")
    )
    dask_future = create_dask_task(dask_task_resources)
    assert dask_future

    # this should trigger a scaling up as we have no nodes
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=ComputationalAutoscaling()
    )

    # nothing runs
    assert not all_instances["Reservations"]
    # check there is an error in the logs
    error_messages = [
        x.message for x in caplog.get_records("call") if x.levelno == logging.ERROR
    ]
    assert len(error_messages) == 1
    assert "Unexpected error:" in error_messages[0]


async def test_cluster_does_not_scale_up_if_defined_instance_is_not_fitting_resources(
    minimal_configuration: None,
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    create_dask_task: Callable[[DaskTaskResources], distributed.Future],
    create_dask_task_resources: Callable[..., DaskTaskResources],
    ec2_client: EC2Client,
    faker: Faker,
    caplog: pytest.LogCaptureFixture,
):
    # we have nothing running now
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]

    # create a task that needs more power
    dask_task_resources = create_dask_task_resources(
        "t2.xlarge", parse_obj_as(ByteSize, "128GiB")
    )
    dask_future = create_dask_task(dask_task_resources)
    assert dask_future

    # this should trigger a scaling up as we have no nodes
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=ComputationalAutoscaling()
    )

    # nothing runs
    assert not all_instances["Reservations"]
    # check there is an error in the logs
    error_messages = [
        x.message for x in caplog.get_records("call") if x.levelno == logging.ERROR
    ]
    assert len(error_messages) == 1
    assert "Unexpected error:" in error_messages[0]


@dataclass(frozen=True)
class _ScaleUpParams:
    task_resources: Resources
    num_tasks: int
    expected_instance_type: str
    expected_num_instances: int


def _dask_task_resources_from_resources(resources: Resources) -> DaskTaskResources:
    return {
        res_key.upper(): res_value for res_key, res_value in resources.dict().items()
    }


@pytest.fixture
def patch_ec2_client_launch_instancess_min_number_of_instances(
    mocker: MockerFixture,
) -> mock.Mock:
    """the moto library always returns min number of instances instead of max number of instances which makes
    it difficult to test scaling to multiple of machines. this should help"""
    original_fct = SimcoreEC2API.launch_instances

    async def _change_parameters(*args, **kwargs) -> list[EC2InstanceData]:
        new_kwargs = kwargs | {"min_number_of_instances": kwargs["number_of_instances"]}
        print(f"patching launch_instances with: {new_kwargs}")
        return await original_fct(*args, **new_kwargs)

    return mocker.patch.object(
        SimcoreEC2API,
        "launch_instances",
        autospec=True,
        side_effect=_change_parameters,
    )


@pytest.mark.parametrize(
    "scale_up_params",
    [
        pytest.param(
            _ScaleUpParams(
                task_resources=Resources(cpus=5, ram=parse_obj_as(ByteSize, "36Gib")),
                num_tasks=10,
                expected_instance_type="g3.4xlarge",
                expected_num_instances=4,
            ),
            id="isolve",
        )
    ],
)
async def test_cluster_scaling_up_starts_multiple_instances(
    patch_ec2_client_launch_instancess_min_number_of_instances: mock.Mock,
    minimal_configuration: None,
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    create_dask_task: Callable[[DaskTaskResources], distributed.Future],
    ec2_client: EC2Client,
    mock_docker_tag_node: mock.Mock,
    scale_up_params: _ScaleUpParams,
    mock_rabbitmq_post_message: mock.Mock,
    mock_docker_find_node_with_name_returns_fake_node: mock.Mock,
    mock_docker_set_node_availability: mock.Mock,
    dask_spec_local_cluster: distributed.SpecCluster,
    ec2_instance_custom_tags: dict[str, str],
):
    # we have nothing running now
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]

    # create several tasks that needs more power
    dask_futures = await asyncio.gather(
        *(
            asyncio.get_event_loop().run_in_executor(
                None,
                create_dask_task,
                _dask_task_resources_from_resources(scale_up_params.task_resources),
            )
            for _ in range(scale_up_params.num_tasks)
        )
    )
    assert dask_futures

    # run the code
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=ComputationalAutoscaling()
    )

    # check the instances were started
    await assert_autoscaled_computational_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=scale_up_params.expected_num_instances,
        expected_instance_type="g3.4xlarge",
        expected_instance_state="running",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
    )

    # as the new node is already running, but is not yet connected, hence not tagged and drained
    mock_docker_find_node_with_name_returns_fake_node.assert_not_called()
    mock_docker_tag_node.assert_not_called()
    mock_docker_set_node_availability.assert_not_called()
    # check rabbit messages were sent
    _assert_rabbit_autoscaling_message_sent(
        mock_rabbitmq_post_message,
        app_settings,
        initialized_app,
        dask_spec_local_cluster.scheduler_address,
        instances_pending=scale_up_params.expected_num_instances,
    )
    mock_rabbitmq_post_message.reset_mock()


async def test_cluster_scaling_up_more_than_allowed_max_starts_max_instances_and_not_more(
    patch_ec2_client_launch_instancess_min_number_of_instances: mock.Mock,
    minimal_configuration: None,
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    create_dask_task: Callable[[DaskTaskResources], distributed.Future],
    ec2_client: EC2Client,
    dask_spec_local_cluster: distributed.SpecCluster,
    create_dask_task_resources: Callable[..., DaskTaskResources],
    mock_docker_tag_node: mock.Mock,
    mock_rabbitmq_post_message: mock.Mock,
    mock_docker_find_node_with_name_returns_fake_node: mock.Mock,
    mock_docker_set_node_availability: mock.Mock,
    mock_docker_compute_node_used_resources: mock.Mock,
    mock_dask_get_worker_has_results_in_memory: mock.Mock,
    mock_dask_get_worker_used_resources: mock.Mock,
    ec2_instance_custom_tags: dict[str, str],
):
    ec2_instance_type = "r5n.8xlarge"

    # we have nothing running now
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    assert app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES > 0
    num_tasks = 3 * app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES

    # create the tasks
    task_futures = await asyncio.gather(
        *(
            _create_task_with_resources(
                ec2_client,
                ec2_instance_type,
                None,
                create_dask_task_resources,
                create_dask_task,
            )
            for _ in range(num_tasks)
        )
    )
    assert all(task_futures)

    # this should trigger a scaling up as we have no nodes
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=ComputationalAutoscaling()
    )
    await assert_autoscaled_computational_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES,
        expected_instance_type=ec2_instance_type,
        expected_instance_state="running",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
    )
    # as the new node is already running, but is not yet connected, hence not tagged and drained
    mock_docker_find_node_with_name_returns_fake_node.assert_not_called()
    mock_docker_tag_node.assert_not_called()
    mock_docker_set_node_availability.assert_not_called()
    mock_docker_compute_node_used_resources.assert_not_called()
    mock_dask_get_worker_has_results_in_memory.assert_not_called()
    mock_dask_get_worker_used_resources.assert_not_called()
    # check rabbit messages were sent
    _assert_rabbit_autoscaling_message_sent(
        mock_rabbitmq_post_message,
        app_settings,
        initialized_app,
        dask_spec_local_cluster.scheduler_address,
        instances_running=0,
        instances_pending=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES,
    )
    mock_rabbitmq_post_message.reset_mock()

    # 2. calling this multiple times should do nothing
    num_useless_calls = 10
    for _ in range(num_useless_calls):
        await auto_scale_cluster(
            app=initialized_app, auto_scaling_mode=ComputationalAutoscaling()
        )
    await assert_autoscaled_computational_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES,
        expected_instance_type=ec2_instance_type,
        expected_instance_state="running",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
    )


async def test_cluster_scaling_up_more_than_allowed_with_multiple_types_max_starts_max_instances_and_not_more(
    patch_ec2_client_launch_instancess_min_number_of_instances: mock.Mock,
    minimal_configuration: None,
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    create_dask_task: Callable[[DaskTaskResources], distributed.Future],
    ec2_client: EC2Client,
    dask_spec_local_cluster: distributed.SpecCluster,
    create_dask_task_resources: Callable[..., DaskTaskResources],
    mock_docker_tag_node: mock.Mock,
    mock_rabbitmq_post_message: mock.Mock,
    mock_docker_find_node_with_name_returns_fake_node: mock.Mock,
    mock_docker_set_node_availability: mock.Mock,
    mock_docker_compute_node_used_resources: mock.Mock,
    mock_dask_get_worker_has_results_in_memory: mock.Mock,
    mock_dask_get_worker_used_resources: mock.Mock,
    aws_allowed_ec2_instance_type_names: list[InstanceTypeType],
):
    # we have nothing running now
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    assert app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES > 0
    num_tasks = 3 * app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES

    # create the tasks
    task_futures = await asyncio.gather(
        *(
            _create_task_with_resources(
                ec2_client,
                ec2_instance_type,
                None,
                create_dask_task_resources,
                create_dask_task,
            )
            for ec2_instance_type in aws_allowed_ec2_instance_type_names
            for _ in range(num_tasks)
        )
    )
    assert all(task_futures)

    # this should trigger a scaling up as we have no nodes
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=ComputationalAutoscaling()
    )

    # one of each type is created with some that will have 2 instances
    all_instances = await ec2_client.describe_instances()
    assert len(all_instances["Reservations"]) == len(
        aws_allowed_ec2_instance_type_names
    )
    instances_found = defaultdict(int)
    for reservation in all_instances["Reservations"]:
        assert "Instances" in reservation
        for instance in reservation["Instances"]:
            assert "InstanceType" in instance
            instance_type = instance["InstanceType"]
            instances_found[instance_type] += 1

    assert sorted(instances_found.keys()) == sorted(aws_allowed_ec2_instance_type_names)
    assert (
        sum(instances_found.values())
        == app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES
    )

    # as the new node is already running, but is not yet connected, hence not tagged and drained
    mock_docker_find_node_with_name_returns_fake_node.assert_not_called()
    mock_docker_tag_node.assert_not_called()
    mock_docker_set_node_availability.assert_not_called()
    mock_docker_compute_node_used_resources.assert_not_called()
    mock_dask_get_worker_has_results_in_memory.assert_not_called()
    mock_dask_get_worker_used_resources.assert_not_called()
    # check rabbit messages were sent
    _assert_rabbit_autoscaling_message_sent(
        mock_rabbitmq_post_message,
        app_settings,
        initialized_app,
        dask_spec_local_cluster.scheduler_address,
        instances_running=0,
        instances_pending=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES,
    )
    mock_rabbitmq_post_message.reset_mock()

    # 2. calling this multiple times should do nothing
    num_useless_calls = 10
    for _ in range(num_useless_calls):
        await auto_scale_cluster(
            app=initialized_app, auto_scaling_mode=ComputationalAutoscaling()
        )
    all_instances = await ec2_client.describe_instances()
    assert len(all_instances["Reservations"]) == len(
        aws_allowed_ec2_instance_type_names
    )


@pytest.mark.parametrize(
    "dask_task_imposed_ec2_type, dask_ram, expected_ec2_type",
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
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    create_dask_task: Callable[[DaskTaskResources], distributed.Future],
    ec2_client: EC2Client,
    dask_task_imposed_ec2_type: InstanceTypeType | None,
    dask_ram: ByteSize | None,
    create_dask_task_resources: Callable[..., DaskTaskResources],
    dask_spec_local_cluster: distributed.SpecCluster,
    expected_ec2_type: InstanceTypeType,
    mock_find_node_with_name_returns_none: mock.Mock,
    mock_docker_tag_node: mock.Mock,
    mock_rabbitmq_post_message: mock.Mock,
    short_ec2_instance_max_start_time: datetime.timedelta,
    ec2_instance_custom_tags: dict[str, str],
):
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    assert (
        short_ec2_instance_max_start_time
        == app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_START_TIME
    )
    # we have nothing running now
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]
    # create a task that needs more power
    dask_future = await _create_task_with_resources(
        ec2_client,
        dask_task_imposed_ec2_type,
        dask_ram,
        create_dask_task_resources,
        create_dask_task,
    )
    assert dask_future
    # this should trigger a scaling up as we have no nodes
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=ComputationalAutoscaling()
    )

    # check the instance was started and we have exactly 1
    instances = await assert_autoscaled_computational_ec2_instances(
        ec2_client,
        expected_num_reservations=1,
        expected_num_instances=1,
        expected_instance_type=expected_ec2_type,
        expected_instance_state="running",
        expected_additional_tag_keys=list(ec2_instance_custom_tags),
    )

    # as the new node is already running, but is not yet connected, hence not tagged and drained
    mock_find_node_with_name_returns_none.assert_not_called()
    mock_docker_tag_node.assert_not_called()
    # check rabbit messages were sent
    _assert_rabbit_autoscaling_message_sent(
        mock_rabbitmq_post_message,
        app_settings,
        initialized_app,
        dask_spec_local_cluster.scheduler_address,
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
            app=initialized_app, auto_scaling_mode=ComputationalAutoscaling()
        )
        # there should be no scaling up, since there is already a pending instance
        instances = await assert_autoscaled_computational_ec2_instances(
            ec2_client,
            expected_num_reservations=1,
            expected_num_instances=1,
            expected_instance_type=expected_ec2_type,
            expected_instance_state="running",
            expected_additional_tag_keys=list(ec2_instance_custom_tags),
        )
        assert mock_find_node_with_name_returns_none.call_count == i + 1
        mock_docker_tag_node.assert_not_called()
        _assert_rabbit_autoscaling_message_sent(
            mock_rabbitmq_post_message,
            app_settings,
            initialized_app,
            dask_spec_local_cluster.scheduler_address,
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
        app=initialized_app, auto_scaling_mode=ComputationalAutoscaling()
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
