# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import itertools
from copy import deepcopy
from typing import Any, AsyncIterator, Awaitable, Callable, Mapping, Optional

import aiodocker
import psutil
import pytest
from deepdiff import DeepDiff
from faker import Faker
from pydantic import ByteSize
from simcore_service_autoscaling.utils_docker import (
    ClusterResources,
    Node,
    compute_cluster_total_resources,
    compute_cluster_used_resources,
    get_monitored_nodes,
    pending_service_tasks_with_insufficient_resources,
)


@pytest.fixture
async def host_node(
    docker_swarm: None,
    async_docker_client: aiodocker.Docker,
) -> Node:
    nodes = await async_docker_client.nodes.list()
    assert len(nodes) == 1
    return nodes[0]


@pytest.fixture
async def create_node_labels(
    host_node: Node,
    async_docker_client: aiodocker.Docker,
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


async def test_get_monitored_nodes(
    docker_swarm: None,
    host_node: Node,
):
    monitored_nodes = await get_monitored_nodes(node_labels=[])
    assert len(monitored_nodes) == 1
    assert monitored_nodes[0] == host_node


async def test_get_monitored_nodes_with_invalid_label(
    docker_swarm: None,
    host_node: Node,
    faker: Faker,
):
    monitored_nodes = await get_monitored_nodes(
        node_labels=faker.pylist(allowed_types=(str,))
    )
    assert len(monitored_nodes) == 0


async def test_get_monitored_nodes_with_valid_label(
    docker_swarm: None,
    host_node: Node,
    faker: Faker,
    create_node_labels: Callable[[list[str]], Awaitable[None]],
):
    labels = faker.pylist(allowed_types=(str,))
    await create_node_labels(labels)
    monitored_nodes = await get_monitored_nodes(node_labels=labels)
    assert len(monitored_nodes) == 1

    # this is the host node with some keys slightly changed
    diff = DeepDiff(
        monitored_nodes[0],
        host_node,
        exclude_paths={
            "Index",
            "UpdatedAt",
            "Version",
            "root['Spec']['Name']",
            "root['Spec']['Labels']",
        },
    )
    assert not diff, f"{diff}"


async def test_pending_service_task_with_insufficient_resources_with_no_service(
    docker_swarm: None,
    host_node: Node,
):
    assert (
        await pending_service_tasks_with_insufficient_resources(service_labels=[]) == []
    )


async def test_pending_service_task_with_insufficient_resources_with_service_lacking_resource(
    docker_swarm: None,
    host_node: Node,
    async_docker_client: aiodocker.Docker,
    create_service: Callable[[dict[str, Any]], Awaitable[Mapping[str, Any]]],
    task_template: dict[str, Any],
    create_task_resources: Callable[[int], dict[str, Any]],
    assert_for_service_state: Callable[
        [aiodocker.Docker, Mapping[str, Any], list[str]], Awaitable[None]
    ],
):
    # a service with no reservation is not "using" resource for docker, therefore we should not find it
    service_with_no_resources = await create_service(task_template)
    await assert_for_service_state(
        async_docker_client, service_with_no_resources, ["running"]
    )
    assert (
        await pending_service_tasks_with_insufficient_resources(service_labels=[]) == []
    )
    # a service that requires a huge amount of resources will not run, and we should find it
    task_template_with_too_many_resource = task_template | create_task_resources(1000)
    service_with_too_many_resources = await create_service(
        task_template_with_too_many_resource
    )
    # a service will complain only once its task reaches the pending state, so let's wait a bit
    await assert_for_service_state(
        async_docker_client,
        service_with_too_many_resources,
        ["pending"],
    )
    service_tasks = await async_docker_client.tasks.list(
        filters={"service": service_with_too_many_resources["Spec"]["Name"]}
    )
    assert service_tasks
    assert len(service_tasks) == 1

    # now we should find that service
    pending_tasks = await pending_service_tasks_with_insufficient_resources(
        service_labels=[]
    )
    assert pending_tasks
    assert len(pending_tasks) == 1
    diff = DeepDiff(
        pending_tasks[0],
        service_tasks[0],
        exclude_paths={
            "UpdatedAt",
            "Version",
            "root['Status']['Err']",
            "root['Status']['Timestamp']",
        },
    )
    assert not diff, f"{diff}"


async def test_pending_service_task_with_insufficient_resources_with_labelled_services(
    docker_swarm: None,
    host_node: Node,
    async_docker_client: aiodocker.Docker,
    create_service: Callable[
        [dict[str, Any], Optional[dict[str, str]]], Awaitable[Mapping[str, Any]]
    ],
    task_template: dict[str, Any],
    create_task_resources: Callable[[int], dict[str, Any]],
    assert_for_service_state: Callable[
        [aiodocker.Docker, Mapping[str, Any], list[str]], Awaitable[None]
    ],
    faker: Faker,
):
    service_labels: dict[str, str] = faker.pydict(allowed_types=(str,))
    task_template_with_too_many_resource = task_template | create_task_resources(1000)

    # start a service without labels, we should not find it
    service_with_no_labels = await create_service(
        task_template_with_too_many_resource, None
    )
    # wait for it to be unhappy about resources
    await assert_for_service_state(
        async_docker_client, service_with_no_labels, ["pending"]
    )
    assert (
        await pending_service_tasks_with_insufficient_resources(
            service_labels=list(service_labels)
        )
        == []
    )

    # start a service with a part of the labels, we should not find it
    partial_service_labels = dict(itertools.islice(service_labels.items(), 2))
    service_with_partial_labels = await create_service(
        task_template_with_too_many_resource, partial_service_labels
    )
    # wait for it to be unhappy about resources
    await assert_for_service_state(
        async_docker_client, service_with_partial_labels, ["pending"]
    )
    assert (
        await pending_service_tasks_with_insufficient_resources(
            service_labels=list(service_labels)
        )
        == []
    )

    service_with_labels = await create_service(
        task_template_with_too_many_resource, service_labels
    )
    await assert_for_service_state(
        async_docker_client, service_with_labels, ["pending"]
    )

    pending_tasks = await pending_service_tasks_with_insufficient_resources(
        service_labels=list(service_labels)
    )

    service_tasks = await async_docker_client.tasks.list(
        filters={"service": service_with_labels["Spec"]["Name"]}
    )
    assert service_tasks
    assert len(service_tasks) == 1
    assert pending_tasks
    assert len(pending_tasks) == 1
    diff = DeepDiff(
        pending_tasks[0],
        service_tasks[0],
        exclude_paths={
            "UpdatedAt",
            "Version",
            "root['Status']['Err']",
            "root['Status']['Timestamp']",
        },
    )
    assert not diff, f"{diff}"


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
    host_node: Node,
):
    cluster_used_resources = await compute_cluster_used_resources([host_node["ID"]])
    assert cluster_used_resources == ClusterResources(
        total_cpus=0, total_ram=ByteSize(0), node_ids=[host_node["ID"]]
    )


async def test_compute_cluster_used_resources_with_services_running(
    async_docker_client: aiodocker.Docker,
    host_node: Node,
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
