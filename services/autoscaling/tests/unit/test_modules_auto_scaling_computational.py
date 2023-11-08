# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements


import asyncio
import base64
import datetime
import logging
from collections.abc import Callable, Iterator
from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from unittest import mock

import distributed
import pytest
from dask_task_models_library.constants import DASK_TASK_EC2_RESOURCE_RESTRICTION_KEY
from faker import Faker
from fastapi import FastAPI
from models_library.docker import DOCKER_TASK_EC2_INSTANCE_TYPE_PLACEMENT_CONSTRAINT_KEY
from models_library.generated_models.docker_rest_api import Availability
from models_library.generated_models.docker_rest_api import Node as DockerNode
from models_library.generated_models.docker_rest_api import NodeState, NodeStatus
from models_library.rabbitmq_messages import RabbitAutoscalingStatusMessage
from pydantic import ByteSize, parse_obj_as
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from simcore_service_autoscaling.core.settings import ApplicationSettings
from simcore_service_autoscaling.models import (
    AssociatedInstance,
    Cluster,
    EC2InstanceData,
    Resources,
)
from simcore_service_autoscaling.modules.auto_scaling_core import (
    _deactivate_empty_nodes,
    auto_scale_cluster,
)
from simcore_service_autoscaling.modules.auto_scaling_mode_computational import (
    ComputationalAutoscaling,
)
from simcore_service_autoscaling.modules.dask import DaskTaskResources
from simcore_service_autoscaling.modules.docker import get_docker_client
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
    docker_swarm: None,
    enabled_computational_mode: EnvVarsDict,
    local_dask_scheduler_server_envs: EnvVarsDict,
    disabled_rabbitmq: None,
    disable_dynamic_service_background_task: None,
    aws_subnet_id: str,
    aws_security_group_id: str,
    aws_ami_id: str,
    aws_allowed_ec2_instance_type_names_env: list[str],
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


@pytest.fixture
def empty_cluster(cluster: Callable[..., Cluster]) -> Cluster:
    return cluster()


async def _assert_ec2_instances(
    ec2_client: EC2Client,
    *,
    num_reservations: int,
    num_instances: int,
    instance_type: str,
    instance_state: str,
) -> list[str]:
    all_instances = await ec2_client.describe_instances()

    assert len(all_instances["Reservations"]) == num_reservations
    internal_dns_names = []
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
                "io.simcore.autoscaling.dask-scheduler_url",
                "Name",
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
def mock_tag_node(mocker: MockerFixture) -> mock.Mock:
    async def fake_tag_node(*args, **kwargs) -> DockerNode:
        return args[1]

    return mocker.patch(
        "simcore_service_autoscaling.modules.auto_scaling_core.utils_docker.tag_node",
        autospec=True,
        side_effect=fake_tag_node,
    )


@pytest.fixture
def mock_find_node_with_name(
    mocker: MockerFixture, fake_node: DockerNode
) -> Iterator[mock.Mock]:
    return mocker.patch(
        "simcore_service_autoscaling.modules.auto_scaling_core.utils_docker.find_node_with_name",
        autospec=True,
        return_value=fake_node,
    )


@pytest.fixture
def mock_set_node_availability(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "simcore_service_autoscaling.modules.auto_scaling_core.utils_docker.set_node_availability",
        autospec=True,
    )


@pytest.fixture
def mock_cluster_used_resources(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "simcore_service_autoscaling.modules.auto_scaling_core.utils_docker.compute_cluster_used_resources",
        autospec=True,
        return_value=Resources.create_as_empty(),
    )


@pytest.fixture
def mock_compute_node_used_resources(mocker: MockerFixture) -> mock.Mock:
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


async def test_cluster_scaling_with_no_tasks_does_nothing(
    minimal_configuration: None,
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    mock_start_aws_instance: mock.Mock,
    mock_terminate_instances: mock.Mock,
    mock_rabbitmq_post_message: mock.Mock,
    dask_spec_local_cluster: distributed.SpecCluster,
):
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=ComputationalAutoscaling()
    )
    mock_start_aws_instance.assert_not_called()
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
    mock_start_aws_instance: mock.Mock,
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
    mock_start_aws_instance.assert_not_called()
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
            resources[DASK_TASK_EC2_RESOURCE_RESTRICTION_KEY] = ec2_instance_type
        return resources

    return _do


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
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    create_dask_task: Callable[[DaskTaskResources], distributed.Future],
    ec2_client: EC2Client,
    mock_tag_node: mock.Mock,
    fake_node: DockerNode,
    mock_rabbitmq_post_message: mock.Mock,
    mock_find_node_with_name: mock.Mock,
    mock_set_node_availability: mock.Mock,
    mock_compute_node_used_resources: mock.Mock,
    mocker: MockerFixture,
    dask_spec_local_cluster: distributed.SpecCluster,
    create_dask_task_resources: Callable[..., DaskTaskResources],
    dask_task_imposed_ec2_type: InstanceTypeType | None,
    dask_ram: ByteSize,
    expected_ec2_type: InstanceTypeType,
):
    # we have nothing running now
    all_instances = await ec2_client.describe_instances()
    assert not all_instances["Reservations"]

    # create a task that needs more power
    dask_task_resources = create_dask_task_resources(
        dask_task_imposed_ec2_type, dask_ram
    )
    dask_future = create_dask_task(dask_task_resources)
    assert dask_future

    # this should trigger a scaling up as we have no nodes
    await auto_scale_cluster(
        app=initialized_app, auto_scaling_mode=ComputationalAutoscaling()
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
    mock_tag_node.assert_not_called()
    mock_set_node_availability.assert_not_called()
    mock_compute_node_used_resources.assert_not_called()
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
    mock_compute_node_used_resources.assert_not_called()
    internal_dns_names = await _assert_ec2_instances(
        ec2_client,
        num_reservations=1,
        num_instances=1,
        instance_type=expected_ec2_type,
        instance_state="running",
    )
    assert len(internal_dns_names) == 1
    internal_dns_name = internal_dns_names[0].removesuffix(".ec2.internal")

    # the node is tagged and made active right away since we still have the pending task
    mock_find_node_with_name.assert_called_once()
    mock_find_node_with_name.reset_mock()
    expected_docker_node_tags = {
        DOCKER_TASK_EC2_INSTANCE_TYPE_PLACEMENT_CONSTRAINT_KEY: expected_ec2_type
    }
    mock_tag_node.assert_called_once_with(
        get_docker_client(initialized_app),
        fake_node,
        tags=expected_docker_node_tags,
        available=False,
    )
    mock_tag_node.reset_mock()
    mock_set_node_availability.assert_called_once_with(
        get_docker_client(initialized_app), fake_node, available=True
    )
    mock_set_node_availability.reset_mock()

    # in this case there is no message sent since the worker was not started yet
    mock_rabbitmq_post_message.assert_not_called()

    # now we have 1 monitored node that needs to be mocked
    auto_scaling_mode = ComputationalAutoscaling()
    mocker.patch.object(
        auto_scaling_mode,
        "get_monitored_nodes",
        autospec=True,
        return_value=[fake_node],
    )
    fake_node.Status = NodeStatus(State=NodeState.ready, Message=None, Addr=None)
    assert fake_node.Spec
    fake_node.Spec.Availability = Availability.active
    assert fake_node.Description
    fake_node.Description.Hostname = internal_dns_name

    # 3. calling this multiple times should do nothing
    for _ in range(10):
        await auto_scale_cluster(
            app=initialized_app, auto_scaling_mode=auto_scaling_mode
        )
    mock_compute_node_used_resources.assert_not_called()
    mock_find_node_with_name.assert_not_called()
    mock_tag_node.assert_not_called()
    mock_set_node_availability.assert_not_called()
    # check the number of instances did not change and is still running
    await _assert_ec2_instances(
        ec2_client,
        num_reservations=1,
        num_instances=1,
        instance_type=expected_ec2_type,
        instance_state="running",
    )

    # check no rabbit messages were sent
    # NOTE: we currently have no real dask-worker here
    mock_rabbitmq_post_message.assert_not_called()

    #
    # 4. now scaling down, as we deleted all the tasks
    #
    del dask_future
    # the worker will not be found since there is none in this testing environment, but it should not raise
    await auto_scale_cluster(app=initialized_app, auto_scaling_mode=auto_scaling_mode)
    # check the number of instances did not change and is still running
    await _assert_ec2_instances(
        ec2_client,
        num_reservations=1,
        num_instances=1,
        instance_type=expected_ec2_type,
        instance_state="running",
    )
    # now mock the call so that it triggers deactivation
    mocked_dask_get_worker_still_has_results_in_memory = mocker.patch(
        "simcore_service_autoscaling.modules.dask.get_worker_still_has_results_in_memory",
        return_value=0,
        autospec=True,
    )
    mocked_dask_get_worker_used_resources = mocker.patch(
        "simcore_service_autoscaling.modules.dask.get_worker_used_resources",
        return_value=Resources.create_as_empty(),
        autospec=True,
    )
    await auto_scale_cluster(app=initialized_app, auto_scaling_mode=auto_scaling_mode)
    mocked_dask_get_worker_still_has_results_in_memory.assert_called()
    assert mocked_dask_get_worker_still_has_results_in_memory.call_count == 2
    mocked_dask_get_worker_still_has_results_in_memory.reset_mock()
    mocked_dask_get_worker_used_resources.assert_called()
    assert mocked_dask_get_worker_used_resources.call_count == 2
    mocked_dask_get_worker_used_resources.reset_mock()
    # the node shall be set to drain, but not yet terminated
    mock_set_node_availability.assert_called_once_with(
        get_docker_client(initialized_app), fake_node, available=False
    )
    mock_set_node_availability.reset_mock()
    await _assert_ec2_instances(
        ec2_client,
        num_reservations=1,
        num_instances=1,
        instance_type=expected_ec2_type,
        instance_state="running",
    )

    # we artifically set the node to drain
    fake_node.Spec.Availability = Availability.drain
    fake_node.UpdatedAt = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
    # the node will be not be terminated beforet the timeout triggers
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
    fake_node.UpdatedAt = (
        datetime.datetime.now(tz=datetime.timezone.utc)
        - app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
        - datetime.timedelta(seconds=1)
    ).isoformat()
    await auto_scale_cluster(app=initialized_app, auto_scaling_mode=auto_scaling_mode)
    mocked_docker_remove_node.assert_called_once_with(mock.ANY, [fake_node], force=True)
    await _assert_ec2_instances(
        ec2_client,
        num_reservations=1,
        num_instances=1,
        instance_type=expected_ec2_type,
        instance_state="terminated",
    )


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
    minimal_configuration: None,
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    create_dask_task: Callable[[DaskTaskResources], distributed.Future],
    ec2_client: EC2Client,
    mock_tag_node: mock.Mock,
    scale_up_params: _ScaleUpParams,
    mock_rabbitmq_post_message: mock.Mock,
    mock_find_node_with_name: mock.Mock,
    mock_set_node_availability: mock.Mock,
    dask_spec_local_cluster: distributed.SpecCluster,
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
        dask_spec_local_cluster.scheduler_address,
        instances_pending=scale_up_params.expected_num_instances,
    )
    mock_rabbitmq_post_message.reset_mock()


@pytest.fixture
def fake_associated_host_instance(
    host_node: DockerNode,
    fake_localhost_ec2_instance_data: EC2InstanceData,
) -> AssociatedInstance:
    return AssociatedInstance(
        host_node,
        fake_localhost_ec2_instance_data,
    )


async def test__deactivate_empty_nodes(
    minimal_configuration: None,
    initialized_app: FastAPI,
    cluster: Callable[..., Cluster],
    host_node: DockerNode,
    fake_associated_host_instance: AssociatedInstance,
    mock_set_node_availability: mock.Mock,
):
    # since we have no service running, we expect the passed node to be set to drain
    active_cluster = cluster(active_nodes=[fake_associated_host_instance])
    updated_cluster = await _deactivate_empty_nodes(
        initialized_app, active_cluster, ComputationalAutoscaling()
    )
    assert not updated_cluster.active_nodes
    assert updated_cluster.drained_nodes == active_cluster.active_nodes
    mock_set_node_availability.assert_called_once_with(
        mock.ANY, host_node, available=False
    )


async def test__deactivate_empty_nodes_with_finished_tasks_should_not_deactivate_until_tasks_are_retrieved(
    minimal_configuration: None,
    initialized_app: FastAPI,
    cluster: Callable[..., Cluster],
    host_node: DockerNode,
    fake_associated_host_instance: AssociatedInstance,
    mock_set_node_availability: mock.Mock,
    create_dask_task: Callable[[DaskTaskResources], distributed.Future],
):
    dask_future = create_dask_task({})
    assert dask_future
    # NOTE: this sucks, but it seems that as soon as we use any method of the future it returns the data to the caller
    await asyncio.sleep(4)
    # since we have result still in memory, the node shall remain active
    active_cluster = cluster(active_nodes=[fake_associated_host_instance])

    updated_cluster = await _deactivate_empty_nodes(
        initialized_app, deepcopy(active_cluster), ComputationalAutoscaling()
    )
    assert updated_cluster.active_nodes
    mock_set_node_availability.assert_not_called()

    # now removing the dask_future shall remove the result from the memory
    del dask_future
    await asyncio.sleep(4)
    updated_cluster = await _deactivate_empty_nodes(
        initialized_app, deepcopy(active_cluster), ComputationalAutoscaling()
    )
    assert not updated_cluster.active_nodes
    assert updated_cluster.drained_nodes == active_cluster.active_nodes
    mock_set_node_availability.assert_called_once_with(
        mock.ANY, host_node, available=False
    )
