# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from simcore_service_autoscaling.utils_docker import (
    ClusterResources,
    eval_cluster_resources,
    need_resources,
)


async def test_eval_cluster_resource_without_swarm():
    assert not await need_resources()

    resources: ClusterResources = await eval_cluster_resources()
    assert not resources.nodes_ids
