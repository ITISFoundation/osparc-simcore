# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Callable

import pytest
from faker import Faker
from models_library.rpc_schemas_clusters_keeper.clusters import ClusterState
from pydantic import SecretStr
from simcore_service_clusters_keeper.models import EC2InstanceData
from simcore_service_clusters_keeper.utils.clusters import (
    create_cluster_from_ec2_instance,
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
def test_create_cluster_from_ec2_instance(
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
    faker: Faker,
    ec2_state: InstanceStateNameType,
    expected_cluster_state: ClusterState,
):
    instance_data = fake_ec2_instance_data(state=ec2_state)
    cluster_instance = create_cluster_from_ec2_instance(
        instance_data,
        faker.pyint(),
        faker.pyint(),
        SecretStr(faker.password()),
        faker.pybool(),
    )
    assert cluster_instance
    assert cluster_instance.state is expected_cluster_state
