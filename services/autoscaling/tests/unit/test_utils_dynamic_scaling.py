# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Callable

import pytest
from faker import Faker
from models_library.generated_models.docker_rest_api import Node, Task
from pydantic import ByteSize
from pytest_mock import MockerFixture
from simcore_service_autoscaling.core.errors import Ec2InvalidDnsNameError
from simcore_service_autoscaling.models import EC2InstanceType
from simcore_service_autoscaling.modules.ec2 import EC2InstanceData
from simcore_service_autoscaling.utils.dynamic_scaling import (
    associate_ec2_instances_with_nodes,
    node_host_name_from_ec2_private_dns,
    try_assigning_task_to_pending_instances,
)


@pytest.fixture
def node(faker: Faker) -> Callable[..., Node]:
    def _creator(**overrides) -> Node:
        return Node(
            **(
                {
                    "ID": faker.uuid4(),
                    "CreatedAt": f"{faker.date_time()}",
                    "UpdatedAt": f"{faker.date_time()}",
                    "Description": {"Hostname": faker.pystr()},
                }
                | overrides
            )
        )

    return _creator


@pytest.fixture
def fake_task(faker: Faker) -> Callable[..., Task]:
    def _creator(**overrides) -> Task:
        return Task(
            **({"ID": faker.uuid4(), "Name": faker.pystr(), "Spec": {}} | overrides)
        )

    return _creator


def test_node_host_name_from_ec2_private_dns(
    fake_ec2_instance_data: Callable[..., EC2InstanceData]
):
    instance = fake_ec2_instance_data(
        aws_private_dns="ip-10-12-32-3.internal-data",
    )
    assert node_host_name_from_ec2_private_dns(instance) == "ip-10-12-32-3"


def test_node_host_name_from_ec2_private_dns_raises_with_invalid_name(
    fake_ec2_instance_data: Callable[..., EC2InstanceData]
):
    instance = fake_ec2_instance_data()
    with pytest.raises(Ec2InvalidDnsNameError):
        node_host_name_from_ec2_private_dns(instance)


@pytest.mark.parametrize("valid_ec2_dns", [True, False])
async def test_associate_ec2_instances_with_nodes_with_no_correspondence(
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
    node: Callable[..., Node],
    valid_ec2_dns: bool,
):
    nodes = [node() for _ in range(10)]
    ec2_instances = [
        fake_ec2_instance_data(aws_private_dns=f"ip-10-12-32-{n+1}.internal-data")
        if valid_ec2_dns
        else fake_ec2_instance_data()
        for n in range(10)
    ]

    (
        associated_instances,
        non_associated_instances,
    ) = await associate_ec2_instances_with_nodes(nodes, ec2_instances)

    assert not associated_instances
    assert non_associated_instances
    assert len(non_associated_instances) == len(ec2_instances)


async def test_associate_ec2_instances_with_corresponding_nodes(
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
    node: Callable[..., Node],
):
    nodes = []
    ec2_instances = []
    for n in range(10):
        host_name = f"ip-10-12-32-{n+1}"
        nodes.append(node(Description={"Hostname": host_name}))
        ec2_instances.append(
            fake_ec2_instance_data(aws_private_dns=f"{host_name}.internal-data")
        )

    (
        associated_instances,
        non_associated_instances,
    ) = await associate_ec2_instances_with_nodes(nodes, ec2_instances)

    assert associated_instances
    assert not non_associated_instances
    assert len(associated_instances) == len(ec2_instances)
    assert len(associated_instances) == len(nodes)
    for associated_instance in associated_instances:
        assert associated_instance.node.Description
        assert associated_instance.node.Description.Hostname
        assert (
            associated_instance.node.Description.Hostname
            in associated_instance.ec2_instance.aws_private_dns
        )


async def test_try_assigning_task_to_pending_instances_with_no_instances(
    mocker: MockerFixture,
    fake_task: Callable[..., Task],
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
):
    fake_app = mocker.Mock()
    pending_task = fake_task()
    assert (
        await try_assigning_task_to_pending_instances(fake_app, pending_task, [], {})
        is False
    )


async def test_try_assigning_task_to_pending_instances(
    mocker: MockerFixture,
    fake_task: Callable[..., Task],
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
):
    fake_app = mocker.Mock()
    pending_task = fake_task(
        Spec={"Resources": {"Reservations": {"NanoCPUs": 2 * 1e9}}}
    )
    fake_instance = fake_ec2_instance_data()
    pending_instance_to_tasks: list[tuple[EC2InstanceData, list[Task]]] = [
        (fake_instance, [])
    ]
    type_to_instance_map = {
        fake_instance.type: EC2InstanceType(
            name=fake_instance.type, cpus=4, ram=ByteSize(1024 * 1024)
        )
    }
    # calling once should allow to add that task to the instance
    assert (
        await try_assigning_task_to_pending_instances(
            fake_app, pending_task, pending_instance_to_tasks, type_to_instance_map
        )
        is True
    )
    # calling a second time as well should allow to add that task to the instance
    assert (
        await try_assigning_task_to_pending_instances(
            fake_app, pending_task, pending_instance_to_tasks, type_to_instance_map
        )
        is True
    )
    # calling a third time should fail
    assert (
        await try_assigning_task_to_pending_instances(
            fake_app, pending_task, pending_instance_to_tasks, type_to_instance_map
        )
        is False
    )
