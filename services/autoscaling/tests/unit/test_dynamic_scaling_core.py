# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import asyncio
import datetime
from dataclasses import dataclass
from typing import Any, AsyncIterator, Awaitable, Callable, Iterator
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
from simcore_service_autoscaling.dynamic_scaling_core import (
    _activate_drained_nodes,
    _deactivate_empty_nodes,
    _find_terminateable_instances,
    _try_scale_down_cluster,
    cluster_scaling_from_labelled_services,
)
from simcore_service_autoscaling.models import AssociatedInstance, Resources
from simcore_service_autoscaling.modules.docker import (
    AutoscalingDocker,
    get_docker_client,
)
from simcore_service_autoscaling.modules.ec2 import EC2InstanceData
from types_aiobotocore_ec2.client import EC2Client


@pytest.fixture
def mock_terminate_instances(mocker: MockerFixture) -> Iterator[mock.Mock]:
    mocked_terminate_instance = mocker.patch(
        "simcore_service_autoscaling.modules.ec2.AutoscalingEC2.terminate_instances",
        autospec=True,
    )
    yield mocked_terminate_instance


@pytest.fixture
def mock_start_aws_instance(
    mocker: MockerFixture,
    aws_instance_private_dns: str,
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
) -> Iterator[mock.Mock]:
    mocked_start_aws_instance = mocker.patch(
        "simcore_service_autoscaling.modules.ec2.AutoscalingEC2.start_aws_instance",
        autospec=True,
        return_value=fake_ec2_instance_data(aws_private_dns=aws_instance_private_dns),
    )
    yield mocked_start_aws_instance


@pytest.fixture
def mock_rabbitmq_post_message(mocker: MockerFixture) -> Iterator[mock.Mock]:
    mocked_post_message = mocker.patch(
        "simcore_service_autoscaling.utils.rabbitmq.post_message", autospec=True
    )
    yield mocked_post_message


@pytest.fixture
def mock_try_get_node_with_name(
    mocker: MockerFixture, fake_node: Node
) -> Iterator[mock.Mock]:
    mocked_wait_for_node = mocker.patch(
        "simcore_service_autoscaling.dynamic_scaling_core.utils_docker.try_get_node_with_name",
        autospec=True,
        return_value=fake_node,
    )
    yield mocked_wait_for_node


@pytest.fixture
def mock_tag_node(mocker: MockerFixture) -> Iterator[mock.Mock]:
    async def fake_tag_node(*args, **kwargs) -> Node:
        return args[1]

    mocked_tag_node = mocker.patch(
        "simcore_service_autoscaling.utils.utils_docker.tag_node",
        autospec=True,
        side_effect=fake_tag_node,
    )
    yield mocked_tag_node


@pytest.fixture
def mock_set_node_availability(mocker: MockerFixture) -> Iterator[mock.Mock]:
    mocked_tag_node = mocker.patch(
        "simcore_service_autoscaling.utils.utils_docker.set_node_availability",
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
def mock_machines_buffer(monkeypatch: pytest.MonkeyPatch) -> Iterator[int]:
    num_machines_in_buffer = 5
    monkeypatch.setenv("EC2_INSTANCES_MACHINES_BUFFER", f"{num_machines_in_buffer}")
    yield num_machines_in_buffer


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
) -> Iterator[None]:
    yield


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
    await cluster_scaling_from_labelled_services(initialized_app)
    mock_start_aws_instance.assert_not_called()
    mock_terminate_instances.assert_not_called()
    _assert_rabbit_autoscaling_message_sent(
        mock_rabbitmq_post_message, app_settings, initialized_app
    )


# async def test_cluster_scaling_from_labelled_services_with_no_services_and_machine_buffer_starts_expected_machines(
#     minimal_configuration: None,
#     mock_machines_buffer: int,
#     app_settings: ApplicationSettings,
#     initialized_app: FastAPI,
#     aws_allowed_ec2_instance_type_names: list[str],
#     mock_start_aws_instance: mock.Mock,
#     mock_terminate_instances: mock.Mock,
#     mock_rabbitmq_post_message: mock.Mock,
# ):
#     assert app_settings.AUTOSCALING_EC2_INSTANCES
#     assert (
#         app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER
#         == mock_machines_buffer
#     )
#     await cluster_scaling_from_labelled_services(initialized_app)
#     mock_start_aws_instance.assert_called_once()
#     assert "number_of_instances" in mock_start_aws_instance.call_args[1]
#     assert (
#         mock_start_aws_instance.call_args[1]["number_of_instances"]
#         == mock_machines_buffer
#     )
#     assert "instance_type" in mock_start_aws_instance.call_args[1]
#     assert (
#         mock_start_aws_instance.call_args[1]["instance_type"]
#         == app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES[0]
#     )
#     mock_terminate_instances.assert_not_called()
#     _assert_rabbit_autoscaling_message_sent(
#         mock_rabbitmq_post_message, app_settings, initialized_app
#     )
#     # now calling the function again should do nothing
#     mock_start_aws_instance.reset_mock()
#     await cluster_scaling_from_labelled_services(initialized_app)
#     await cluster_scaling_from_labelled_services(initialized_app)
#     mock_start_aws_instance.assert_not_called()
#     mock_terminate_instances.assert_not_called()


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

    await cluster_scaling_from_labelled_services(initialized_app)
    mock_start_aws_instance.assert_not_called()
    mock_terminate_instances.assert_not_called()
    _assert_rabbit_autoscaling_message_sent(
        mock_rabbitmq_post_message, app_settings, initialized_app
    )


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
    mock_try_get_node_with_name: mock.Mock,
    mock_set_node_availability: mock.Mock,
    mocker: MockerFixture,
    faker: Faker,
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
    await cluster_scaling_from_labelled_services(initialized_app)

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
        "Name",
    ]
    for tag_dict in running_instance["Tags"]:
        assert "Key" in tag_dict
        assert "Value" in tag_dict

        assert tag_dict["Key"] in expected_tag_keys
    assert "PrivateDnsName" in running_instance
    instance_private_dns_name = running_instance["PrivateDnsName"]
    assert instance_private_dns_name.endswith(".ec2.internal")

    # as the new node is already running, but is not yet connected, hence not tagged and drained
    mock_try_get_node_with_name.assert_not_called()
    mock_tag_node.assert_not_called()
    mock_set_node_availability.assert_not_called()
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
    fake_cluster_used_resource = Resources(
        cpus=faker.pyint(min_value=1), ram=ByteSize(faker.pyint(min_value=1000))
    )
    mocker.patch(
        "simcore_service_autoscaling.utils.utils_docker.compute_cluster_used_resources",
        autospec=True,
        return_value=fake_cluster_used_resource,
    )
    await cluster_scaling_from_labelled_services(initialized_app)
    all_instances = await ec2_client.describe_instances()
    assert (
        len(all_instances["Reservations"]) == 1
    ), "the cluster was scaled up again, that is bad!"
    mock_try_get_node_with_name.assert_called_once_with(
        get_docker_client(initialized_app),
        instance_private_dns_name.rstrip(".ec2.internal"),
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
        available=False,
    )

    # expect the node to be set available
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
        nodes_drained=1,  # NOTE: this value is wrong, but that is only a test artifact as we do not have a docker swarm mock
        cluster_total_resources={
            "cpus": fake_node.Description.Resources.NanoCPUs / 1e9,
            "ram": fake_node.Description.Resources.MemoryBytes,
        },
        cluster_used_resources={
            "cpus": float(fake_cluster_used_resource.cpus),
            "ram": fake_cluster_used_resource.ram,
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
    mock_try_get_node_with_name: mock.Mock,
    mock_set_node_availability: mock.Mock,
    mocker: MockerFixture,
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
    await cluster_scaling_from_labelled_services(initialized_app)

    # check the instances were started
    all_instances = await ec2_client.describe_instances()
    assert len(all_instances["Reservations"]) == 1
    running_instances = all_instances["Reservations"][0]
    assert "Instances" in running_instances
    assert len(running_instances["Instances"]) == scale_up_params.expected_num_instances

    # check the instances
    all_private_dns_names = []
    for instance in running_instances["Instances"]:
        assert "InstanceType" in instance
        assert instance["InstanceType"] == scale_up_params.expected_instance_type
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
        all_private_dns_names.append(instance_private_dns_name)

    # as the new node is already running, but is not yet connected, hence not tagged and drained
    mock_try_get_node_with_name.assert_not_called()
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
    host_node: Node,
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
    mock_tag_node: mock.Mock,
):
    # since we have no service running, we expect the passed node to be set to drain
    await _deactivate_empty_nodes(
        initialized_app,
        [AssociatedInstance(host_node, fake_ec2_instance_data())],
    )
    mock_tag_node.assert_called_once_with(mock.ANY, host_node, tags={}, available=False)


async def test__deactivate_empty_nodes_to_drain_when_services_running_are_missing_labels(
    minimal_configuration: None,
    initialized_app: FastAPI,
    host_node: Node,
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
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

    await _deactivate_empty_nodes(
        initialized_app, [AssociatedInstance(host_node, fake_ec2_instance_data())]
    )
    mock_tag_node.assert_called_once_with(mock.ANY, host_node, tags={}, available=False)


async def test__deactivate_empty_nodes_does_not_drain_if_service_is_running_with_correct_labels(
    minimal_configuration: None,
    app_settings: ApplicationSettings,
    initialized_app: FastAPI,
    host_node: Node,
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
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
    await _deactivate_empty_nodes(
        initialized_app, [AssociatedInstance(host_node, fake_ec2_instance_data())]
    )
    mock_tag_node.assert_not_called()


async def test__find_terminateable_nodes_with_no_hosts(
    minimal_configuration: None,
    initialized_app: FastAPI,
    host_node: Node,
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
):
    # there is no node to terminate, since the host is not an EC2 instance and is not drained
    assert (
        await _find_terminateable_instances(
            initialized_app, [AssociatedInstance(host_node, fake_ec2_instance_data())]
        )
        == []
    )


async def test__find_terminateable_nodes_with_drained_host_and_in_ec2(
    minimal_configuration: None,
    initialized_app: FastAPI,
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
    attached_ec2_nowish = AssociatedInstance(
        drained_host_node,
        fake_ec2_instance_data(
            launch_time=datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
        ),
    )
    assert (
        await _find_terminateable_instances(initialized_app, [attached_ec2_nowish])
        == []
    )

    # if the instance started just after the termination time, even on several days, it is not terminateable
    attached_ec2_long_time_ago_but_not_inthe_window = AssociatedInstance(
        drained_host_node,
        fake_ec2_instance_data(
            launch_time=datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
            - app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
            - datetime.timedelta(days=21)
            + datetime.timedelta(seconds=10)
        ),
    )
    assert (
        await _find_terminateable_instances(
            initialized_app, [attached_ec2_long_time_ago_but_not_inthe_window]
        )
        == []
    )

    # if the instance started just before the termination time, even on several days, it is terminateable
    attached_ec2_long_time_ago_terminateable = AssociatedInstance(
        drained_host_node,
        fake_ec2_instance_data(
            launch_time=datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
            - app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
            - datetime.timedelta(days=21)
            - datetime.timedelta(seconds=10),
        ),
    )

    assert await _find_terminateable_instances(
        initialized_app, [attached_ec2_long_time_ago_terminateable]
    ) == [attached_ec2_long_time_ago_terminateable]


async def test__try_scale_down_cluster_with_no_nodes(
    minimal_configuration: None,
    initialized_app: FastAPI,
    mock_remove_nodes: mock.Mock,
):
    # this shall work as is
    await _try_scale_down_cluster(initialized_app, [])
    mock_remove_nodes.assert_not_called()


async def test__try_scale_down_cluster(
    minimal_configuration: None,
    initialized_app: FastAPI,
    drained_host_node: Node,
    mock_terminate_instances: mock.Mock,
    mock_remove_nodes: mock.Mock,
    app_settings: ApplicationSettings,
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
):
    assert app_settings.AUTOSCALING_EC2_INSTANCES
    assert (
        app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
        > datetime.timedelta(seconds=10)
    ), "this tests relies on the fact that the time before termination is above 10 seconds"

    await _try_scale_down_cluster(
        initialized_app,
        [
            AssociatedInstance(
                drained_host_node,
                fake_ec2_instance_data(
                    launch_time=datetime.datetime.utcnow().replace(
                        tzinfo=datetime.timezone.utc
                    )
                    - app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
                    - datetime.timedelta(days=21)
                    - datetime.timedelta(seconds=10)
                ),
            )
        ],
    )
    mock_terminate_instances.assert_called_once()
    mock_remove_nodes.assert_called_once()


async def test__activate_drained_nodes_with_no_tasks(
    minimal_configuration: None,
    initialized_app: FastAPI,
    host_node: Node,
    mock_tag_node: mock.Mock,
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
):
    # no tasks, does nothing and returns True
    assert await _activate_drained_nodes(initialized_app, [], []) == []
    assert (
        await _activate_drained_nodes(
            initialized_app,
            [AssociatedInstance(host_node, fake_ec2_instance_data())],
            [],
        )
        == []
    )
    mock_tag_node.assert_not_called()


async def test__activate_drained_nodes_with_no_drained_nodes(
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
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
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
        await _activate_drained_nodes(
            initialized_app,
            [AssociatedInstance(host_node, fake_ec2_instance_data())],
            service_tasks,
        )
        == []
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


async def test__activate_drained_nodes_with_drained_node(
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
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
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
        await _activate_drained_nodes(
            initialized_app,
            [AssociatedInstance(drained_host_node, fake_ec2_instance_data())],
            service_tasks,
        )
        == service_tasks
    )
    mock_tag_node.assert_called_once_with(
        mock.ANY, drained_host_node, tags={}, available=True
    )
