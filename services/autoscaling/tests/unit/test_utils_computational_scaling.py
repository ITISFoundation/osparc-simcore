# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import datetime
from collections.abc import Callable
from unittest import mock

import pytest
from faker import Faker
from models_library.generated_models.docker_rest_api import Node as DockerNode
from pydantic import ByteSize, parse_obj_as
from pytest_mock import MockerFixture
from simcore_service_autoscaling.models import (
    AssociatedInstance,
    DaskTask,
    DaskTaskResources,
    EC2InstanceData,
    EC2InstanceType,
    Resources,
)
from simcore_service_autoscaling.utils.computational_scaling import (
    _DEFAULT_MAX_CPU,
    _DEFAULT_MAX_RAM,
    get_max_resources_from_dask_task,
    try_assigning_task_to_instance_types,
    try_assigning_task_to_node,
    try_assigning_task_to_pending_instances,
)


@pytest.mark.parametrize(
    "dask_task, expected_resource",
    [
        pytest.param(
            DaskTask(task_id="fake", required_resources=DaskTaskResources()),
            Resources(
                cpus=_DEFAULT_MAX_CPU, ram=parse_obj_as(ByteSize, _DEFAULT_MAX_RAM)
            ),
            id="missing resources returns defaults",
        ),
        pytest.param(
            DaskTask(task_id="fake", required_resources={"CPU": 2.5}),
            Resources(cpus=2.5, ram=parse_obj_as(ByteSize, _DEFAULT_MAX_RAM)),
            id="only cpus defined",
        ),
        pytest.param(
            DaskTask(
                task_id="fake",
                required_resources={"CPU": 2.5, "RAM": 2 * 1024 * 1024 * 1024},
            ),
            Resources(cpus=2.5, ram=parse_obj_as(ByteSize, "2GiB")),
            id="cpu and ram defined",
        ),
        pytest.param(
            DaskTask(
                task_id="fake",
                required_resources={"CPU": 2.5, "ram": 2 * 1024 * 1024 * 1024},
            ),
            Resources(cpus=2.5, ram=parse_obj_as(ByteSize, _DEFAULT_MAX_RAM)),
            id="invalid naming",
        ),
    ],
)
def test_get_max_resources_from_dask_task(
    dask_task: DaskTask, expected_resource: Resources
):
    assert get_max_resources_from_dask_task(dask_task) == expected_resource


@pytest.fixture
def fake_app(mocker: MockerFixture) -> mock.Mock:
    app = mocker.Mock()
    app.state.settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_START_TIME = (
        datetime.timedelta(minutes=1)
    )
    return app


@pytest.fixture
def fake_task(faker: Faker) -> Callable[..., DaskTask]:
    def _creator(**overrides) -> DaskTask:
        return DaskTask(
            **(
                {
                    "task_id": faker.uuid4(),
                    "required_resources": DaskTaskResources(faker.pydict()),
                }
                | overrides
            )
        )

    return _creator


async def test_try_assigning_task_to_node_with_no_instances(
    fake_task: Callable[..., DaskTask],
):
    task = fake_task()
    assert try_assigning_task_to_node(task, []) is False


@pytest.fixture
def fake_associated_host_instance(
    host_node: DockerNode,
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
) -> AssociatedInstance:
    return AssociatedInstance(
        host_node,
        fake_ec2_instance_data(),
    )


async def test_try_assigning_task_to_node(
    fake_task: Callable[..., DaskTask],
    fake_associated_host_instance: AssociatedInstance,
):
    task = fake_task(required_resources={"CPU": 2})
    assert fake_associated_host_instance.node.Description
    assert fake_associated_host_instance.node.Description.Resources
    # we set the node to have 4 CPUs
    fake_associated_host_instance.node.Description.Resources.NanoCPUs = int(4e9)
    instance_to_tasks: list[tuple[AssociatedInstance, list[DaskTask]]] = [
        (fake_associated_host_instance, [])
    ]
    assert try_assigning_task_to_node(task, instance_to_tasks) is True
    assert instance_to_tasks[0][1] == [task]
    # this should work again
    assert try_assigning_task_to_node(task, instance_to_tasks) is True
    assert instance_to_tasks[0][1] == [task, task]
    # this should now fail
    assert try_assigning_task_to_node(task, instance_to_tasks) is False
    assert instance_to_tasks[0][1] == [task, task]


async def test_try_assigning_task_to_pending_instances_with_no_instances(
    fake_app: mock.Mock,
    fake_task: Callable[..., DaskTask],
):
    task = fake_task()
    assert (
        await try_assigning_task_to_pending_instances(
            fake_app, task, [], {}, notify_progress=True
        )
        is False
    )


async def test_try_assigning_task_to_pending_instances(
    fake_app: mock.Mock,
    fake_task: Callable[..., DaskTask],
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
):
    task = fake_task(required_resources={"CPU": 2})
    ec2_instance = fake_ec2_instance_data()
    pending_instance_to_tasks: list[tuple[EC2InstanceData, list[DaskTask]]] = [
        (ec2_instance, [])
    ]
    type_to_instance_map = {
        ec2_instance.type: EC2InstanceType(
            name=ec2_instance.type, cpus=4, ram=ByteSize(1024 * 1024)
        )
    }
    # calling once should allow to add that task to the instance
    assert (
        await try_assigning_task_to_pending_instances(
            fake_app,
            task,
            pending_instance_to_tasks,
            type_to_instance_map,
            notify_progress=True,
        )
        is True
    )
    assert pending_instance_to_tasks[0][1] == [task]
    # calling a second time as well should allow to add that task to the instance
    assert (
        await try_assigning_task_to_pending_instances(
            fake_app,
            task,
            pending_instance_to_tasks,
            type_to_instance_map,
            notify_progress=True,
        )
        is True
    )
    assert pending_instance_to_tasks[0][1] == [task, task]
    # calling a third time should fail
    assert (
        await try_assigning_task_to_pending_instances(
            fake_app,
            task,
            pending_instance_to_tasks,
            type_to_instance_map,
            notify_progress=True,
        )
        is False
    )
    assert pending_instance_to_tasks[0][1] == [task, task]


def test_try_assigning_task_to_instance_types_with_empty_types(
    fake_task: Callable[..., DaskTask]
):
    task = fake_task(required_resources={"CPU": 2})
    assert try_assigning_task_to_instance_types(task, []) is False


def test_try_assigning_task_to_instance_types(
    fake_task: Callable[..., DaskTask], faker: Faker
):
    task = fake_task(required_resources={"CPU": 2})
    # create an instance type with some CPUs
    fake_instance_type = EC2InstanceType(
        name=faker.name(), cpus=6, ram=parse_obj_as(ByteSize, "2GiB")
    )
    instance_type_to_tasks: list[tuple[EC2InstanceType, list[DaskTask]]] = [
        (fake_instance_type, [])
    ]
    # now this should work 3 times
    assert try_assigning_task_to_instance_types(task, instance_type_to_tasks) is True
    assert instance_type_to_tasks[0][1] == [task]
    assert try_assigning_task_to_instance_types(task, instance_type_to_tasks) is True
    assert instance_type_to_tasks[0][1] == [task, task]
    assert try_assigning_task_to_instance_types(task, instance_type_to_tasks) is True
    assert instance_type_to_tasks[0][1] == [task, task, task]
    # now it should fail
    assert try_assigning_task_to_instance_types(task, instance_type_to_tasks) is False
    assert instance_type_to_tasks[0][1] == [task, task, task]
