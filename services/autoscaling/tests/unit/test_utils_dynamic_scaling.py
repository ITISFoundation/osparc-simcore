# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Callable

import pytest
from faker import Faker
from models_library.generated_models.docker_rest_api import Node, NodeDescription
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
            ID=faker.uuid4(),
            CreatedAt=f"{faker.date_time()}",
            UpdatedAt=f"{faker.date_time()}",
            Description=NodeDescription(Hostname=faker.pystr()),
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
