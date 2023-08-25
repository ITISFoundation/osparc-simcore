# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from simcore_service_clusters_keeper.models import (
    ClusterState,
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
