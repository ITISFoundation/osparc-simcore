# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from copy import deepcopy
from typing import Any, AsyncIterator, Awaitable, Callable, Mapping

import aiodocker
import psutil
import pytest
from faker import Faker
from pydantic import ByteSize
from simcore_service_autoscaling.utils_docker import (
    ClusterResources,
    compute_cluster_total_resources,
    compute_cluster_used_resources,
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


async def test_compute_cluster_total_resources_with_no_label_return_host_resources(
    docker_swarm: None,
):
    cluster_resources = await compute_cluster_total_resources(node_labels=[])
    assert cluster_resources.total_cpus == psutil.cpu_count()
    assert cluster_resources.total_ram == psutil.virtual_memory().total
    assert cluster_resources.node_ids
    assert len(cluster_resources.node_ids) == 1


async def test_compute_cluster_total_resources_with_label_returns_no_resources(
    docker_swarm: None, faker: Faker
):
    cluster_resources = await compute_cluster_total_resources(
        node_labels=faker.pylist(allowed_types=(str,))
    )
    assert cluster_resources.total_cpus == 0
    assert cluster_resources.total_ram == 0
    assert not cluster_resources.node_ids


@pytest.fixture
async def host_node(
    docker_swarm: None, async_docker_client: aiodocker.Docker
) -> Mapping[str, Any]:
    nodes = await async_docker_client.nodes.list()
    assert len(nodes) == 1
    return nodes[0]


@pytest.fixture
async def create_node_labels(
    host_node: Mapping[str, Any], async_docker_client: aiodocker.Docker
) -> AsyncIterator[Callable[[list[str]], Awaitable[None]]]:
    old_labels = deepcopy(host_node["Spec"]["Labels"])

    async def _creator(labels: list[str]) -> None:
        await async_docker_client.nodes.update(
            node_id=host_node["ID"],
            version=host_node["Version"]["Index"],
            spec={
                "Name": "foo",
                "Availability": host_node["Spec"]["Availability"],
                "Role": host_node["Spec"]["Role"],
                "Labels": {f"{label}": "true" for label in labels},
            },
        )
        return

    yield _creator
    # revert labels
    nodes = await async_docker_client.nodes.list()
    assert nodes
    assert len(nodes) == 1
    current_node = nodes[0]
    await async_docker_client.nodes.update(
        node_id=current_node["ID"],
        version=current_node["Version"]["Index"],
        spec={
            "Availability": current_node["Spec"]["Availability"],
            "Role": current_node["Spec"]["Role"],
            "Labels": old_labels,
        },
    )


async def test_compute_cluster_total_resources_with_correct_label_return_host_resources(
    docker_swarm: None,
    faker: Faker,
    create_node_labels: Callable[[list[str]], Awaitable[None]],
):
    labels = faker.pylist(allowed_types=(str,))
    await create_node_labels(labels)
    cluster_resources = await compute_cluster_total_resources(node_labels=labels)
    assert cluster_resources.total_cpus == psutil.cpu_count()
    assert cluster_resources.total_ram == psutil.virtual_memory().total
    assert cluster_resources.node_ids
    assert len(cluster_resources.node_ids) == 1


async def test_compute_cluster_used_resources_with_no_services_running_returns_0(
    host_node: Mapping[str, Any]
):
    cluster_used_resources = await compute_cluster_used_resources([host_node["ID"]])
    assert cluster_used_resources == ClusterResources(
        total_cpus=0, total_ram=ByteSize(0), node_ids=[host_node["ID"]]
    )


async def test_compute_cluster_used_resources_with_services_running(
    async_docker_client: aiodocker.Docker,
    host_node: Mapping[str, Any],
    create_service: Callable[[dict[str, Any]], Awaitable[Mapping[str, Any]]],
    task_template: dict[str, Any],
    create_task_resources: Callable[[int], dict[str, Any]],
    assert_for_service_state: Callable[
        [aiodocker.Docker, Mapping[str, Any], list[str]], Awaitable[None]
    ],
):
    # 1. if we have services with no defined reservations, then we cannot know what they use...
    service_with_no_resources = await create_service(task_template)
    await assert_for_service_state(
        async_docker_client, service_with_no_resources, ["running"]
    )
    cluster_used_resources = await compute_cluster_used_resources([host_node["ID"]])
    assert cluster_used_resources == ClusterResources(
        total_cpus=0, total_ram=ByteSize(0), node_ids=[host_node["ID"]]
    )

    # 2. if we have some services with defined resources, they should be visible
    task_template_with_manageable_resources = task_template | create_task_resources(1)
    service_with_mangeable_resources = await create_service(
        task_template_with_manageable_resources
    )
    await assert_for_service_state(
        async_docker_client, service_with_mangeable_resources, ["pending", "running"]
    )
    cluster_used_resources = await compute_cluster_used_resources([host_node["ID"]])
    assert cluster_used_resources == ClusterResources(
        total_cpus=1, total_ram=ByteSize(0), node_ids=[host_node["ID"]]
    )

    # 3. if we have services that need more resources than available,
    # they should not change what is currently used
    task_template_with_too_many_resource = task_template | create_task_resources(1000)
    service_with_too_many_resources = await create_service(
        task_template_with_too_many_resource
    )
    await assert_for_service_state(
        async_docker_client, service_with_too_many_resources, ["pending"]
    )
    cluster_used_resources = await compute_cluster_used_resources([host_node["ID"]])
    assert cluster_used_resources == ClusterResources(
        total_cpus=1, total_ram=ByteSize(0), node_ids=[host_node["ID"]]
    )
