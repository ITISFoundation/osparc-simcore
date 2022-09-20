# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from simcore_service_autoscaling.utils_docker import (
    check_node_resources,
    need_resources,
)


async def test_it():

    # fixture: docker_client.containers.run("ubuntu:latest", "echo hello world")

    assert not await need_resources()

    nodes = await check_node_resources()
    assert len(nodes.node_ids) == 1
