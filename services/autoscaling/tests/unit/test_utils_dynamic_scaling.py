# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from collections.abc import Callable
from datetime import timedelta

import pytest
from aws_library.ec2.models import EC2InstanceData, Resources
from faker import Faker
from models_library.generated_models.docker_rest_api import Task
from pydantic import ByteSize
from pytest_mock import MockerFixture
from simcore_service_autoscaling.models import AssignedTasksToInstance
from simcore_service_autoscaling.utils.dynamic_scaling import (
    try_assigning_task_to_instances,
)


@pytest.fixture
def fake_task(faker: Faker) -> Callable[..., Task]:
    def _creator(**overrides) -> Task:
        return Task(
            **({"ID": faker.uuid4(), "Name": faker.pystr(), "Spec": {}} | overrides)
        )

    return _creator


async def test_try_assigning_task_to_instances_with_no_instances(
    mocker: MockerFixture,
    fake_task: Callable[..., Task],
):
    fake_app = mocker.Mock()
    pending_task = fake_task()
    assert (
        await try_assigning_task_to_instances(
            fake_app, pending_task, [], notify_progress=True
        )
        is False
    )


async def test_try_assigning_task_to_instances(
    mocker: MockerFixture,
    fake_task: Callable[..., Task],
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
):
    fake_app = mocker.Mock()
    fake_app.state.settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_START_TIME = (
        timedelta(minutes=1)
    )
    pending_task = fake_task(
        Spec={"Resources": {"Reservations": {"NanoCPUs": 2 * 1e9}}}
    )
    fake_instance = fake_ec2_instance_data()
    pending_instance_to_tasks: list[AssignedTasksToInstance] = [
        AssignedTasksToInstance(
            instance=fake_instance,
            assigned_tasks=[],
            available_resources=Resources(cpus=4, ram=ByteSize(1024**3)),
        )
    ]

    # calling once should allow to add that task to the instance
    assert (
        await try_assigning_task_to_instances(
            fake_app,
            pending_task,
            pending_instance_to_tasks,
            notify_progress=True,
        )
        is True
    )
    # calling a second time as well should allow to add that task to the instance
    assert (
        await try_assigning_task_to_instances(
            fake_app,
            pending_task,
            pending_instance_to_tasks,
            notify_progress=True,
        )
        is True
    )
    # calling a third time should fail
    assert (
        await try_assigning_task_to_instances(
            fake_app,
            pending_task,
            pending_instance_to_tasks,
            notify_progress=True,
        )
        is False
    )
