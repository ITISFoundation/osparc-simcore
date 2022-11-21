# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import itertools
from copy import deepcopy
from typing import Any, AsyncIterator, Awaitable, Callable, Mapping, Optional

import aiodocker
import psutil
import pytest
from deepdiff import DeepDiff
from faker import Faker
from models_library.generated_models.docker_rest_api import Task
from pydantic import ByteSize, parse_obj_as
from simcore_service_autoscaling.models import Resources
from simcore_service_autoscaling.utils_docker import (
    Node,
    compute_cluster_total_resources,
    compute_cluster_used_resources,
    compute_node_used_resources,
    get_monitored_nodes,
    get_resources_from_docker_task,
    pending_service_tasks_with_insufficient_resources,
)


@pytest.fixture
async def host_node(
    docker_swarm: None,
    async_docker_client: aiodocker.Docker,
) -> Node:
    nodes = parse_obj_as(list[Node], await async_docker_client.nodes.list())
    assert len(nodes) == 1
    return nodes[0]


@pytest.fixture
async def create_node_labels(
    host_node: Node,
    async_docker_client: aiodocker.Docker,
) -> AsyncIterator[Callable[[list[str]], Awaitable[None]]]:
    assert host_node.Spec
    old_labels = deepcopy(host_node.Spec.Labels)

    async def _creator(labels: list[str]) -> None:
        assert host_node.ID
        assert host_node.Version
        assert host_node.Version.Index
        assert host_node.Spec
        assert host_node.Spec.Role
        assert host_node.Spec.Availability
        await async_docker_client.nodes.update(
            node_id=host_node.ID,
            version=host_node.Version.Index,
            spec={
                "Name": "foo",
                "Availability": host_node.Spec.Availability.value,
                "Role": host_node.Spec.Role.value,
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
    host_node: Node,
):
    monitored_nodes = await get_monitored_nodes(node_labels=[])
    assert len(monitored_nodes) == 1
    assert monitored_nodes[0] == host_node


async def test_get_monitored_nodes_with_invalid_label(
    host_node: Node,
    faker: Faker,
):
    monitored_nodes = await get_monitored_nodes(
        node_labels=faker.pylist(allowed_types=(str,))
    )
    assert len(monitored_nodes) == 0


async def test_get_monitored_nodes_with_valid_label(
    host_node: Node,
    faker: Faker,
    create_node_labels: Callable[[list[str]], Awaitable[None]],
):
    labels = faker.pylist(allowed_types=(str,))
    await create_node_labels(labels)
    monitored_nodes = await get_monitored_nodes(node_labels=labels)
    assert len(monitored_nodes) == 1

    # this is the host node with some keys slightly changed
    EXCLUDED_KEYS = {
        "Index": True,
        "UpdatedAt": True,
        "Version": True,
        "Spec": {"Labels", "Name"},
    }
    assert host_node.dict(exclude=EXCLUDED_KEYS) == monitored_nodes[0].dict(
        exclude=EXCLUDED_KEYS
    )


async def test_pending_service_task_with_insufficient_resources_with_no_service(
    host_node: Node,
):
    assert (
        await pending_service_tasks_with_insufficient_resources(service_labels=[]) == []
    )


async def test_pending_service_task_with_insufficient_resources_with_service_lacking_resource(
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
    service_tasks = parse_obj_as(
        list[Task],
        await async_docker_client.tasks.list(
            filters={"service": service_with_too_many_resources["Spec"]["Name"]}
        ),
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

    service_tasks = parse_obj_as(
        list[Task],
        await async_docker_client.tasks.list(
            filters={"service": service_with_labels["Spec"]["Name"]}
        ),
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


async def test_compute_cluster_total_resources_with_no_nodes_returns_0(
    docker_swarm: None,
):
    cluster_resources = await compute_cluster_total_resources([])
    assert cluster_resources == Resources(cpus=0, ram=ByteSize(0))


async def test_compute_cluster_total_resources_returns_host_resources(host_node: Node):
    cluster_resources = await compute_cluster_total_resources([host_node])
    assert cluster_resources == Resources(
        cpus=psutil.cpu_count(), ram=ByteSize(psutil.virtual_memory().total)
    )


async def test_get_resources_from_docker_task_with_no_reservation_returns_0(
    async_docker_client: aiodocker.Docker,
    create_service: Callable[[dict[str, Any]], Awaitable[Mapping[str, Any]]],
    task_template: dict[str, Any],
    assert_for_service_state: Callable[
        [aiodocker.Docker, Mapping[str, Any], list[str]], Awaitable[None]
    ],
):
    service_with_no_resources = await create_service(task_template)
    await assert_for_service_state(
        async_docker_client, service_with_no_resources, ["running"]
    )
    service_tasks = parse_obj_as(
        list[Task],
        await async_docker_client.tasks.list(
            filters={"service": service_with_no_resources["Spec"]["Name"]}
        ),
    )
    assert service_tasks
    assert len(service_tasks) == 1

    assert get_resources_from_docker_task(service_tasks[0]) == Resources(
        cpus=0, ram=ByteSize(0)
    )


async def test_get_resources_from_docker_task_with_reservations(
    async_docker_client: aiodocker.Docker,
    create_service: Callable[[dict[str, Any]], Awaitable[Mapping[str, Any]]],
    task_template: dict[str, Any],
    create_task_resources: Callable[[int], dict[str, Any]],
    assert_for_service_state: Callable[
        [aiodocker.Docker, Mapping[str, Any], list[str]], Awaitable[None]
    ],
):
    NUM_CPUS = int(psutil.cpu_count() / 2 + 1)
    task_template_with_reservations = task_template | create_task_resources(NUM_CPUS)
    service = await create_service(task_template_with_reservations)
    await assert_for_service_state(async_docker_client, service, ["running"])
    service_tasks = parse_obj_as(
        list[Task],
        await async_docker_client.tasks.list(
            filters={"service": service["Spec"]["Name"]}
        ),
    )
    assert service_tasks
    assert len(service_tasks) == 1

    assert get_resources_from_docker_task(service_tasks[0]) == Resources(
        cpus=NUM_CPUS, ram=ByteSize(0)
    )


async def test_compute_node_used_resources_with_no_service(host_node: Node):
    cluster_resources = await compute_node_used_resources(host_node)
    assert cluster_resources == Resources(cpus=0, ram=ByteSize(0))


async def test_compute_node_used_resources_with_service(
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
    node_used_resources = await compute_node_used_resources(host_node)
    assert node_used_resources == Resources(cpus=0, ram=ByteSize(0))

    # 2. if we have some services with defined resources, they should be visible
    task_template_with_manageable_resources = task_template | create_task_resources(1)
    services_with_manageable_resources = await asyncio.gather(
        *(
            create_service(task_template_with_manageable_resources)
            for cpu in range(psutil.cpu_count())
        )
    )
    await asyncio.gather(
        *(
            assert_for_service_state(
                async_docker_client,
                s,
                ["pending", "running"],
            )
            for s in services_with_manageable_resources
        )
    )
    node_used_resources = await compute_node_used_resources(host_node)
    assert node_used_resources == Resources(cpus=psutil.cpu_count(), ram=ByteSize(0))

    # 3. if we have services that need more resources than available,
    # they should not change what is currently used as they will not run
    task_template_with_too_many_resource = task_template | create_task_resources(1000)
    service_with_too_many_resources = await create_service(
        task_template_with_too_many_resource
    )
    await assert_for_service_state(
        async_docker_client, service_with_too_many_resources, ["pending"]
    )
    node_used_resources = await compute_node_used_resources(host_node)
    assert node_used_resources == Resources(cpus=psutil.cpu_count(), ram=ByteSize(0))


async def test_compute_cluster_used_resources_with_no_nodes_returns_0(
    docker_swarm: None,
):
    cluster_used_resources = await compute_cluster_used_resources([])
    assert cluster_used_resources == Resources(cpus=0, ram=ByteSize(0))


async def test_compute_cluster_used_resources_with_no_services_running_returns_0(
    host_node: Node,
):
    cluster_used_resources = await compute_cluster_used_resources([host_node])
    assert cluster_used_resources == Resources(cpus=0, ram=ByteSize(0))


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
    cluster_used_resources = await compute_cluster_used_resources([host_node])
    assert cluster_used_resources == Resources(cpus=0, ram=ByteSize(0))

    # 2. if we have some services with defined resources, they should be visible
    task_template_with_manageable_resources = task_template | create_task_resources(1)
    services_with_manageable_resources = await asyncio.gather(
        *(
            create_service(task_template_with_manageable_resources)
            for cpu in range(psutil.cpu_count())
        )
    )
    await asyncio.gather(
        *(
            assert_for_service_state(
                async_docker_client,
                s,
                ["pending", "running"],
            )
            for s in services_with_manageable_resources
        )
    )
    cluster_used_resources = await compute_cluster_used_resources([host_node])
    assert cluster_used_resources == Resources(cpus=psutil.cpu_count(), ram=ByteSize(0))

    # 3. if we have services that need more resources than available,
    # they should not change what is currently used
    task_template_with_too_many_resource = task_template | create_task_resources(1000)
    service_with_too_many_resources = await create_service(
        task_template_with_too_many_resource
    )
    await assert_for_service_state(
        async_docker_client, service_with_too_many_resources, ["pending"]
    )
    cluster_used_resources = await compute_cluster_used_resources([host_node])
    assert cluster_used_resources == Resources(cpus=psutil.cpu_count(), ram=ByteSize(0))
