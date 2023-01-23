import pytest
from faker import Faker
from simcore_service_autoscaling.core.errors import Ec2InvalidDnsNameError
from simcore_service_autoscaling.modules.ec2 import EC2InstanceData
from simcore_service_autoscaling.utils.dynamic_scaling import (
    node_host_name_from_ec2_private_dns,
)


def test_node_host_name_from_ec2_private_dns(faker: Faker):
    ec2_instance_data = EC2InstanceData(
        launch_time=faker.date_time(),
        id=faker.uuid4(),
        aws_private_dns="ip-10-12-32-3.internal-data",
        type=faker.pystr(),
        state=faker.pystr(),
    )

    assert node_host_name_from_ec2_private_dns(ec2_instance_data) == "ip-10-12-32-3"


def test_node_host_name_from_ec2_private_dns_raises_with_invalid_name(faker: Faker):
    ec2_instance_data = EC2InstanceData(
        launch_time=faker.date_time(),
        id=faker.uuid4(),
        aws_private_dns=faker.name(),
        type=faker.pystr(),
        state=faker.pystr(),
    )
    with pytest.raises(Ec2InvalidDnsNameError):
        node_host_name_from_ec2_private_dns(ec2_instance_data)
