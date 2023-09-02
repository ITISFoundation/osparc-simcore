# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Callable

import pytest
from faker import Faker
from pydantic import SecretStr
from simcore_service_clusters_keeper.models import (
    ClusterGet,
    ClusterState,
    EC2InstanceData,
    _convert_ec2_state_to_cluster_state,
)
from types_aiobotocore_ec2.literals import InstanceStateNameType


@pytest.mark.parametrize(
    "ec2_state, expected_cluster_state",
    [
        ("pending", ClusterState.STARTED),
        ("running", ClusterState.RUNNING),
        ("shutting-down", ClusterState.STOPPED),
        ("stopped", ClusterState.STOPPED),
        ("stopping", ClusterState.STOPPED),
        ("terminated", ClusterState.STOPPED),
    ],
)
def test__convert_ec2_state_to_cluster_state(
    ec2_state: InstanceStateNameType, expected_cluster_state: ClusterState
):
    assert _convert_ec2_state_to_cluster_state(ec2_state) is expected_cluster_state


def test_from_ec2_instance_data(
    fake_ec2_instance_data: Callable[..., EC2InstanceData], faker: Faker
):
    instance_data = fake_ec2_instance_data()
    cluster_get_instance = ClusterGet.from_ec2_instance_data(
        instance_data, faker.pyint(), faker.pyint(), SecretStr(faker.password())
    )
    assert cluster_get_instance
