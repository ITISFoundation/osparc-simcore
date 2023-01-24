# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Callable

import pytest
from faker import Faker
from models_library.generated_models.docker_rest_api import Node
from simcore_service_autoscaling.core.errors import Ec2InvalidDnsNameError
from simcore_service_autoscaling.modules.ec2 import EC2InstanceData
from simcore_service_autoscaling.utils.dynamic_scaling import (
    associate_ec2_instances_with_nodes,
    node_host_name_from_ec2_private_dns,
)


@pytest.fixture
def ec2_instance_data(faker: Faker) -> Callable[..., EC2InstanceData]:
    def _creator(**overrides) -> EC2InstanceData:
        return EC2InstanceData(
            **(
                {
                    "launch_time": faker.date_time(),
                    "id": faker.uuid4(),
                    "aws_private_dns": faker.name(),
                    "type": faker.pystr(),
                    "state": faker.pystr(),
                }
                | overrides
            )
        )

    return _creator


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


def test_node_host_name_from_ec2_private_dns(
    ec2_instance_data: Callable[..., EC2InstanceData]
):
    instance = ec2_instance_data(
        aws_private_dns="ip-10-12-32-3.internal-data",
    )
    assert node_host_name_from_ec2_private_dns(instance) == "ip-10-12-32-3"


def test_node_host_name_from_ec2_private_dns_raises_with_invalid_name(
    ec2_instance_data: Callable[..., EC2InstanceData]
):
    instance = ec2_instance_data()
    with pytest.raises(Ec2InvalidDnsNameError):
        node_host_name_from_ec2_private_dns(instance)


@pytest.mark.parametrize("valid_ec2_dns", [True, False])
async def test_associate_ec2_instances_with_nodes_with_no_correspondence(
    ec2_instance_data: Callable[..., EC2InstanceData],
    node: Callable[..., Node],
    valid_ec2_dns: bool,
):
    nodes = [node() for _ in range(10)]
    ec2_instances = [
        ec2_instance_data(aws_private_dns=f"ip-10-12-32-{n+1}.internal-data")
        if valid_ec2_dns
        else ec2_instance_data()
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
    ec2_instance_data: Callable[..., EC2InstanceData],
    node: Callable[..., Node],
):
    nodes = []
    ec2_instances = []
    for n in range(10):
        host_name = f"ip-10-12-32-{n+1}"
        nodes.append(node(Description={"Hostname": host_name}))
        ec2_instances.append(
            ec2_instance_data(aws_private_dns=f"{host_name}.internal-data")
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
