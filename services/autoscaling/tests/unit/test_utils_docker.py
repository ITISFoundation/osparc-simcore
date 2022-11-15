# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any, Awaitable, Callable, Mapping

import aiodocker
import psutil
from simcore_service_autoscaling.utils_docker import (
    get_labelized_nodes_resources,
    pending_services_with_insufficient_resources,
)


async def test_pending_services_with_insufficient_resources_with_no_service(
    docker_swarm: None,
):
    assert await pending_services_with_insufficient_resources() == False


async def test_pending_services_with_insufficient_resources_with_service_lacking_resource(
    docker_swarm: None,
    async_docker_client: aiodocker.Docker,
    create_service: Callable[[dict[str, Any]], Awaitable[Mapping[str, Any]]],
    task_template: dict[str, Any],
    create_task_resources: Callable[[int], dict[str, Any]],
    assert_for_service_state: Callable[
        [aiodocker.Docker, Mapping[str, Any], list[str]], Awaitable[None]
    ],
):
    service_with_no_resources = await create_service(task_template)
    await assert_for_service_state(
        async_docker_client, service_with_no_resources, ["running"]
    )
    assert await pending_services_with_insufficient_resources() == False
    task_template_with_too_many_resource = task_template | create_task_resources(1000)
    service_with_too_many_resources = await create_service(
        task_template_with_too_many_resource
    )
    await assert_for_service_state(
        async_docker_client,
        service_with_too_many_resources,
        ["pending"],
    )
    assert await pending_services_with_insufficient_resources() == True


async def test_get_swarm_resources(docker_swarm: None):
    cluster_resources = await get_labelized_nodes_resources(node_labels=[])
    assert cluster_resources.total_cpus == psutil.cpu_count()
    assert cluster_resources.total_ram == psutil.virtual_memory().total
    assert cluster_resources.node_ids
    assert len(cluster_resources.node_ids) == 1
