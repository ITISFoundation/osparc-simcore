# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import datetime
import itertools
import random
from collections.abc import AsyncIterator, Awaitable, Callable
from copy import deepcopy
from typing import Any

import aiodocker
import pytest
from aws_library.ec2.models import Resources
from deepdiff import DeepDiff
from faker import Faker
from models_library.docker import DockerGenericTag, DockerLabelKey
from models_library.generated_models.docker_rest_api import (
    Availability,
    Condition,
    ContainerSpec,
    DiscreteResourceSpec,
    GenericResource,
    GenericResources,
    Isolation,
    Limit,
    Mount,
    NodeDescription,
    NodeState,
    ObjectVersion,
    Placement,
    ResourceObject,
    Resources1,
    RestartPolicy1,
    Service,
    Status1,
    Task,
    TaskSpec,
    TaskState,
    Type1,
    VolumeOptions,
)
from pydantic import ByteSize, parse_obj_as
from pytest_mock.plugin import MockerFixture
from servicelib.docker_utils import to_datetime
from simcore_service_autoscaling.modules.docker import AutoscalingDocker
from simcore_service_autoscaling.utils.utils_docker import (
    Node,
    _by_created_dt,
    _is_task_waiting_for_resources,
    compute_cluster_total_resources,
    compute_cluster_used_resources,
    compute_node_used_resources,
    compute_tasks_needed_resources,
    find_node_with_name,
    get_docker_pull_images_crontab,
    get_docker_pull_images_on_start_bash_command,
    get_docker_swarm_join_bash_command,
    get_max_resources_from_docker_task,
    get_monitored_nodes,
    get_node_total_resources,
    get_worker_nodes,
    pending_service_tasks_with_insufficient_resources,
    remove_nodes,
    tag_node,
)


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
    autoscaling_docker: AutoscalingDocker,
    host_node: Node,
):
    monitored_nodes = await get_monitored_nodes(autoscaling_docker, node_labels=[])
    assert len(monitored_nodes) == 1
    assert monitored_nodes[0] == host_node


async def test_get_monitored_nodes_with_invalid_label(
    autoscaling_docker: AutoscalingDocker,
    host_node: Node,
    faker: Faker,
):
    monitored_nodes = await get_monitored_nodes(
        autoscaling_docker, node_labels=faker.pylist(allowed_types=(str,))
    )
    assert len(monitored_nodes) == 0


async def test_get_monitored_nodes_with_valid_label(
    autoscaling_docker: AutoscalingDocker,
    host_node: Node,
    faker: Faker,
    create_node_labels: Callable[[list[str]], Awaitable[None]],
):
    labels = faker.pylist(allowed_types=(str,))
    await create_node_labels(labels)
    monitored_nodes = await get_monitored_nodes(autoscaling_docker, node_labels=labels)
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


async def test_worker_nodes(
    autoscaling_docker: AutoscalingDocker,
    host_node: Node,
):
    worker_nodes = await get_worker_nodes(autoscaling_docker)
    assert not worker_nodes


async def test_remove_monitored_down_nodes_with_empty_list_does_nothing(
    autoscaling_docker: AutoscalingDocker,
):
    assert await remove_nodes(autoscaling_docker, nodes=[]) == []


async def test_remove_monitored_down_nodes_of_non_down_node_does_nothing(
    autoscaling_docker: AutoscalingDocker,
    host_node: Node,
):
    assert await remove_nodes(autoscaling_docker, nodes=[host_node]) == []


@pytest.fixture
def fake_docker_node(host_node: Node, faker: Faker) -> Node:
    fake_node = host_node.copy(deep=True)
    fake_node.ID = faker.uuid4()
    assert (
        host_node.ID != fake_node.ID
    ), "this should never happen, or you are really unlucky"
    return fake_node


async def test_remove_monitored_down_nodes_of_down_node(
    autoscaling_docker: AutoscalingDocker,
    fake_docker_node: Node,
    mocker: MockerFixture,
):
    mocked_aiodocker = mocker.patch.object(autoscaling_docker, "nodes", autospec=True)
    assert fake_docker_node.Status
    fake_docker_node.Status.State = NodeState.down
    assert fake_docker_node.Status.State == NodeState.down
    assert await remove_nodes(autoscaling_docker, nodes=[fake_docker_node]) == [
        fake_docker_node
    ]
    # NOTE: this is the same as calling with aiodocker.Docker() as docker: docker.nodes.remove()
    mocked_aiodocker.remove.assert_called_once_with(
        node_id=fake_docker_node.ID, force=False
    )


async def test_remove_monitored_down_node_with_unexpected_state_does_nothing(
    autoscaling_docker: AutoscalingDocker,
    fake_docker_node: Node,
):
    assert fake_docker_node.Status
    fake_docker_node.Status = None
    assert not fake_docker_node.Status
    assert await remove_nodes(autoscaling_docker, nodes=[fake_docker_node]) == []


async def test_pending_service_task_with_insufficient_resources_with_no_service(
    autoscaling_docker: AutoscalingDocker,
    host_node: Node,
):
    assert (
        await pending_service_tasks_with_insufficient_resources(
            autoscaling_docker, service_labels=[]
        )
        == []
    )


@pytest.mark.parametrize(
    "placement_constraint, expected_pending_tasks",
    [
        ([], True),
        (["node.id==20398jsdlkjfs"], False),
        (["node.hostname==fake_name"], False),
        (["node.role==manager"], False),
        (["node.platform.os==linux"], True),
        (["node.platform.arch==amd64"], True),
        (["node.labels==amd64"], True),
        (["engine.labels==amd64"], True),
    ],
    ids=str,
)
async def test_pending_service_task_with_placement_constrain_is_skipped(
    host_node: Node,
    autoscaling_docker: AutoscalingDocker,
    create_service: Callable[
        [dict[str, Any], dict[DockerLabelKey, str], str], Awaitable[Service]
    ],
    task_template: dict[str, Any],
    create_task_reservations: Callable[[int, int], dict[str, Any]],
    placement_constraint: list[str],
    expected_pending_tasks: bool,
    faker: Faker,
):
    task_template_with_too_many_resource = task_template | create_task_reservations(
        1000, 0
    )
    if placement_constraint:
        task_template_with_too_many_resource["Placement"] = {
            "Constraints": placement_constraint
        }
    # a service will complain only once its task reaches the pending state
    service_with_too_many_resources = await create_service(
        task_template_with_too_many_resource, {}, "pending"
    )
    assert service_with_too_many_resources.Spec

    pending_tasks = await pending_service_tasks_with_insufficient_resources(
        autoscaling_docker, service_labels=[]
    )
    if expected_pending_tasks:
        assert pending_tasks
    else:
        assert pending_tasks == []


async def test_pending_service_task_with_insufficient_resources_with_service_lacking_resource(
    host_node: Node,
    autoscaling_docker: AutoscalingDocker,
    create_service: Callable[
        [dict[str, Any], dict[DockerLabelKey, str], str], Awaitable[Service]
    ],
    task_template: dict[str, Any],
    create_task_reservations: Callable[[int, int], dict[str, Any]],
):
    # a service with no reservation is not "using" resource for docker, therefore we should not find it
    await create_service(task_template, {}, "running")
    assert (
        await pending_service_tasks_with_insufficient_resources(
            autoscaling_docker, service_labels=[]
        )
        == []
    )
    # a service that requires a huge amount of resources will not run, and we should find it
    task_template_with_too_many_resource = task_template | create_task_reservations(
        1000, 0
    )
    # a service will complain only once its task reaches the pending state
    service_with_too_many_resources = await create_service(
        task_template_with_too_many_resource, {}, "pending"
    )
    assert service_with_too_many_resources.Spec

    service_tasks = parse_obj_as(
        list[Task],
        await autoscaling_docker.tasks.list(
            filters={"service": service_with_too_many_resources.Spec.Name}
        ),
    )
    assert service_tasks
    assert len(service_tasks) == 1

    # now we should find that service
    pending_tasks = await pending_service_tasks_with_insufficient_resources(
        autoscaling_docker, service_labels=[]
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
    autoscaling_docker: AutoscalingDocker,
    create_service: Callable[
        [dict[str, Any], dict[DockerLabelKey, str], str], Awaitable[Service]
    ],
    task_template: dict[str, Any],
    create_task_reservations: Callable[[int, int], dict[str, Any]],
    faker: Faker,
):
    service_labels: dict[DockerLabelKey, str] = faker.pydict(allowed_types=(str,))
    task_template_with_too_many_resource = task_template | create_task_reservations(
        1000, 0
    )

    # start a service without labels, we should not find it
    await create_service(task_template_with_too_many_resource, {}, "pending")
    assert (
        await pending_service_tasks_with_insufficient_resources(
            autoscaling_docker, service_labels=list(service_labels)
        )
        == []
    )

    # start a service with a part of the labels, we should not find it
    partial_service_labels = dict(itertools.islice(service_labels.items(), 2))
    _service_with_partial_labels = await create_service(
        task_template_with_too_many_resource, partial_service_labels, "pending"
    )

    assert (
        await pending_service_tasks_with_insufficient_resources(
            autoscaling_docker, service_labels=list(service_labels)
        )
        == []
    )
    # start a service with the correct labels
    service_with_labels = await create_service(
        task_template_with_too_many_resource, service_labels, "pending"
    )
    assert service_with_labels.Spec
    pending_tasks = await pending_service_tasks_with_insufficient_resources(
        autoscaling_docker, service_labels=list(service_labels)
    )

    service_tasks = parse_obj_as(
        list[Task],
        await autoscaling_docker.tasks.list(
            filters={"service": service_with_labels.Spec.Name}
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


async def test_pending_service_task_with_insufficient_resources_properly_sorts_tasks(
    host_node: Node,
    autoscaling_docker: AutoscalingDocker,
    create_service: Callable[
        [dict[str, Any], dict[DockerLabelKey, str], str], Awaitable[Service]
    ],
    task_template: dict[str, Any],
    create_task_reservations: Callable[[int, int], dict[str, Any]],
    faker: Faker,
):
    service_labels: dict[DockerLabelKey, str] = faker.pydict(allowed_types=(str,))
    task_template_with_too_many_resource = task_template | create_task_reservations(
        1000, 0
    )
    services = await asyncio.gather(
        *(
            create_service(
                task_template_with_too_many_resource, service_labels, "pending"
            )
            for _ in range(190)
        )
    )
    pending_tasks = await pending_service_tasks_with_insufficient_resources(
        autoscaling_docker, service_labels=list(service_labels)
    )

    assert len(pending_tasks) == len(services)
    # check sorting is done by creation date
    last_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        days=1
    )
    for task in pending_tasks:
        assert task.CreatedAt  # NOTE: in this case they are but they might be None
        assert (
            to_datetime(task.CreatedAt).replace(tzinfo=datetime.timezone.utc)
            > last_date
        )
        last_date = to_datetime(task.CreatedAt).replace(tzinfo=datetime.timezone.utc)


def test_safe_sort_key_callback():
    tasks_with_faulty_timestamp = [
        Task(ID=n, CreatedAt=value)  # type: ignore
        for n, value in enumerate(
            [
                # SEE test_to_datetime_conversion_known_errors
                None,
                "2023-03-15 09:20:58.123456",
                "2023-03-15T09:20:58.123456",
                "2023-03-15T09:20:58.123456Z",
                f"{datetime.datetime.now(datetime.timezone.utc)}",
                "corrupted string",
            ]
        )
    ]
    sorted_tasks = sorted(tasks_with_faulty_timestamp, key=_by_created_dt)

    assert len(sorted_tasks) == len(tasks_with_faulty_timestamp)
    assert {t.ID for t in sorted_tasks} == {t.ID for t in tasks_with_faulty_timestamp}


def test_get_node_total_resources(host_node: Node):
    resources = get_node_total_resources(host_node)
    assert host_node.Description
    assert host_node.Description.Resources
    assert host_node.Description.Resources.NanoCPUs
    assert resources.cpus == (host_node.Description.Resources.NanoCPUs / 10**9)
    assert resources.ram == host_node.Description.Resources.MemoryBytes


async def test_compute_cluster_total_resources_with_no_nodes_returns_0(
    docker_swarm: None,
):
    cluster_resources = await compute_cluster_total_resources([])
    assert cluster_resources == Resources(cpus=0, ram=ByteSize(0))


async def test_compute_cluster_total_resources_returns_host_resources(
    host_node: Node, host_cpu_count: int, host_memory_total: ByteSize
):
    cluster_resources = await compute_cluster_total_resources([host_node])
    assert cluster_resources == Resources(cpus=host_cpu_count, ram=host_memory_total)


async def test_get_resources_from_docker_task_with_no_reservation_returns_0(
    autoscaling_docker: AutoscalingDocker,
    create_service: Callable[
        [dict[str, Any], dict[DockerLabelKey, str], str], Awaitable[Service]
    ],
    task_template: dict[str, Any],
):
    service_with_no_resources = await create_service(task_template, {}, "running")
    assert service_with_no_resources.Spec
    service_tasks = parse_obj_as(
        list[Task],
        await autoscaling_docker.tasks.list(
            filters={"service": service_with_no_resources.Spec.Name}
        ),
    )
    assert service_tasks
    assert len(service_tasks) == 1

    assert get_max_resources_from_docker_task(service_tasks[0]) == Resources(
        cpus=0, ram=ByteSize(0)
    )


async def test_get_resources_from_docker_task_with_reservations(
    async_docker_client: aiodocker.Docker,
    create_service: Callable[
        [dict[str, Any], dict[DockerLabelKey, str], str], Awaitable[Service]
    ],
    task_template: dict[str, Any],
    create_task_reservations: Callable[[int, int], dict[str, Any]],
    host_cpu_count: int,
):
    NUM_CPUS = int(host_cpu_count / 2 + 1)
    task_template_with_reservations = task_template | create_task_reservations(
        NUM_CPUS, 0
    )
    service = await create_service(task_template_with_reservations, {}, "running")
    assert service.Spec
    service_tasks = parse_obj_as(
        list[Task],
        await async_docker_client.tasks.list(filters={"service": service.Spec.Name}),
    )
    assert service_tasks
    assert len(service_tasks) == 1

    assert get_max_resources_from_docker_task(service_tasks[0]) == Resources(
        cpus=NUM_CPUS, ram=ByteSize(0)
    )


async def test_get_resources_from_docker_task_with_reservations_and_limits_returns_the_biggest(
    async_docker_client: aiodocker.Docker,
    create_service: Callable[
        [dict[str, Any], dict[DockerLabelKey, str], str], Awaitable[Service]
    ],
    task_template: dict[str, Any],
    create_task_reservations: Callable[[int, int], dict[str, Any]],
    create_task_limits: Callable[[int, int], dict[str, Any]],
    host_cpu_count: int,
):
    NUM_CPUS = int(host_cpu_count / 2 + 0.5)
    task_template_with_reservations = task_template | create_task_reservations(
        NUM_CPUS, 0
    )
    task_template_with_reservations["Resources"] |= create_task_limits(
        host_cpu_count, parse_obj_as(ByteSize, "100Mib")
    )["Resources"]
    service = await create_service(task_template_with_reservations, {}, "running")
    assert service.Spec
    service_tasks = parse_obj_as(
        list[Task],
        await async_docker_client.tasks.list(filters={"service": service.Spec.Name}),
    )
    assert service_tasks
    assert len(service_tasks) == 1

    assert get_max_resources_from_docker_task(service_tasks[0]) == Resources(
        cpus=host_cpu_count, ram=parse_obj_as(ByteSize, "100Mib")
    )


async def test_compute_tasks_needed_resources(
    autoscaling_docker: AutoscalingDocker,
    host_node: Node,
    create_service: Callable[
        [dict[str, Any], dict[DockerLabelKey, str], str], Awaitable[Service]
    ],
    task_template: dict[str, Any],
    create_task_reservations: Callable[[int, int], dict[str, Any]],
    host_cpu_count: int,
    faker: Faker,
):
    service_with_no_resources = await create_service(task_template, {}, "running")
    assert service_with_no_resources.Spec
    service_tasks = parse_obj_as(
        list[Task],
        await autoscaling_docker.tasks.list(
            filters={"service": service_with_no_resources.Spec.Name}
        ),
    )
    assert compute_tasks_needed_resources(service_tasks) == Resources.create_as_empty()

    task_template_with_manageable_resources = task_template | create_task_reservations(
        1, 0
    )
    services = await asyncio.gather(
        *(
            create_service(task_template_with_manageable_resources, {}, "running")
            for cpu in range(host_cpu_count)
        )
    )
    all_tasks = service_tasks
    for s in services:
        service_tasks = parse_obj_as(
            list[Task],
            await autoscaling_docker.tasks.list(filters={"service": s.Spec.Name}),
        )
        assert compute_tasks_needed_resources(service_tasks) == Resources(
            cpus=1, ram=ByteSize(0)
        )
        all_tasks.extend(service_tasks)
    assert compute_tasks_needed_resources(all_tasks) == Resources(
        cpus=host_cpu_count, ram=ByteSize(0)
    )


async def test_compute_node_used_resources_with_no_service(
    autoscaling_docker: AutoscalingDocker, host_node: Node
):
    cluster_resources = await compute_node_used_resources(autoscaling_docker, host_node)
    assert cluster_resources == Resources(cpus=0, ram=ByteSize(0))


async def test_compute_node_used_resources_with_service(
    autoscaling_docker: AutoscalingDocker,
    host_node: Node,
    create_service: Callable[
        [dict[str, Any], dict[DockerLabelKey, str], str], Awaitable[Service]
    ],
    task_template: dict[str, Any],
    create_task_reservations: Callable[[int, int], dict[str, Any]],
    host_cpu_count: int,
    faker: Faker,
):
    # 1. if we have services with no defined reservations, then we cannot know what they use...
    service_with_no_resources = await create_service(task_template, {}, "running")
    node_used_resources = await compute_node_used_resources(
        autoscaling_docker, host_node
    )
    assert node_used_resources == Resources(cpus=0, ram=ByteSize(0))

    # 2. if we have some services with defined resources, they should be visible
    task_template_with_manageable_resources = task_template | create_task_reservations(
        1, 0
    )
    service_labels = faker.pydict(allowed_types=(str,))
    await asyncio.gather(
        *(
            create_service(
                task_template_with_manageable_resources, service_labels, "running"
            )
            for cpu in range(host_cpu_count)
        )
    )
    node_used_resources = await compute_node_used_resources(
        autoscaling_docker, host_node, service_labels=None
    )
    assert node_used_resources == Resources(cpus=host_cpu_count, ram=ByteSize(0))

    # 3. if we look for services with some other label, they should then become invisible again
    node_used_resources = await compute_node_used_resources(
        autoscaling_docker, host_node, service_labels=[faker.pystr()]
    )
    assert node_used_resources == Resources(cpus=0, ram=ByteSize(0))
    # 4. if we look for services with 1 correct label, they should then become visible again
    node_used_resources = await compute_node_used_resources(
        autoscaling_docker,
        host_node,
        service_labels=[random.choice(list(service_labels.keys()))],
    )
    assert node_used_resources == Resources(cpus=host_cpu_count, ram=ByteSize(0))
    # 4. if we look for services with all the correct labels, they should then become visible again
    node_used_resources = await compute_node_used_resources(
        autoscaling_docker, host_node, service_labels=list(service_labels.keys())
    )
    assert node_used_resources == Resources(cpus=host_cpu_count, ram=ByteSize(0))

    # 5. if we have services that need more resources than available,
    # they should not change what is currently used as they will not run
    task_template_with_too_many_resource = task_template | create_task_reservations(
        1000, 0
    )
    service_with_too_many_resources = await create_service(
        task_template_with_too_many_resource, {}, "pending"
    )
    assert service_with_too_many_resources
    node_used_resources = await compute_node_used_resources(
        autoscaling_docker, host_node
    )
    assert node_used_resources == Resources(cpus=host_cpu_count, ram=ByteSize(0))


async def test_compute_cluster_used_resources_with_no_nodes_returns_0(
    autoscaling_docker: AutoscalingDocker,
    docker_swarm: None,
):
    cluster_used_resources = await compute_cluster_used_resources(
        autoscaling_docker, []
    )
    assert cluster_used_resources == Resources(cpus=0, ram=ByteSize(0))


async def test_compute_cluster_used_resources_with_no_services_running_returns_0(
    autoscaling_docker: AutoscalingDocker,
    host_node: Node,
):
    cluster_used_resources = await compute_cluster_used_resources(
        autoscaling_docker, [host_node]
    )
    assert cluster_used_resources == Resources(cpus=0, ram=ByteSize(0))


async def test_compute_cluster_used_resources_with_services_running(
    autoscaling_docker: AutoscalingDocker,
    host_node: Node,
    create_service: Callable[
        [dict[str, Any], dict[DockerLabelKey, str], str], Awaitable[Service]
    ],
    task_template: dict[str, Any],
    create_task_reservations: Callable[[int, int], dict[str, Any]],
    host_cpu_count: int,
):
    # 1. if we have services with no defined reservations, then we cannot know what they use...
    service_with_no_resources = await create_service(task_template, {}, "running")
    assert service_with_no_resources
    cluster_used_resources = await compute_cluster_used_resources(
        autoscaling_docker, [host_node]
    )
    assert cluster_used_resources == Resources(cpus=0, ram=ByteSize(0))

    # 2. if we have some services with defined resources, they should be visible
    task_template_with_manageable_resources = task_template | create_task_reservations(
        1, 0
    )
    await asyncio.gather(
        *(
            create_service(task_template_with_manageable_resources, {}, "running")
            for cpu in range(host_cpu_count)
        )
    )
    cluster_used_resources = await compute_cluster_used_resources(
        autoscaling_docker, [host_node]
    )
    assert cluster_used_resources == Resources(cpus=host_cpu_count, ram=ByteSize(0))

    # 3. if we have services that need more resources than available,
    # they should not change what is currently used
    task_template_with_too_many_resource = task_template | create_task_reservations(
        1000, 0
    )
    service_with_too_many_resources = await create_service(
        task_template_with_too_many_resource, {}, "pending"
    )
    assert service_with_too_many_resources
    cluster_used_resources = await compute_cluster_used_resources(
        autoscaling_docker, [host_node]
    )
    assert cluster_used_resources == Resources(cpus=host_cpu_count, ram=ByteSize(0))


async def test_get_docker_swarm_join_script(host_node: Node):
    join_script = await get_docker_swarm_join_bash_command()
    assert join_script.startswith("docker swarm join")
    assert "--availability=drain" in join_script


async def test_get_docker_swarm_join_script_bad_return_code_raises(
    host_node: Node,
    mocker: MockerFixture,
):
    mocked_asyncio_process = mocker.patch(
        "asyncio.subprocess.Process",
        autospec=True,
    )
    mocked_asyncio_process.return_value.communicate.return_value = (
        b"fakestdout",
        b"fakestderr",
    )
    mocked_asyncio_process.return_value.returncode = 137
    with pytest.raises(RuntimeError, match=r"unexpected error .+"):
        await get_docker_swarm_join_bash_command()
    # NOTE: the sleep here is to provide some time for asyncio to properly close its process communication
    # to silence the warnings
    await asyncio.sleep(2)


async def test_get_docker_swarm_join_script_returning_unexpected_command_raises(
    host_node: Node,
    mocker: MockerFixture,
):
    mocked_asyncio_process = mocker.patch(
        "asyncio.subprocess.Process",
        autospec=True,
    )
    mocked_asyncio_process.return_value.communicate.return_value = (
        b"fakestdout",
        b"fakestderr",
    )
    mocked_asyncio_process.return_value.returncode = 0
    with pytest.raises(RuntimeError, match=r"expected docker .+"):
        await get_docker_swarm_join_bash_command()
    # NOTE: the sleep here is to provide some time for asyncio to properly close its process communication
    # to silence the warnings
    await asyncio.sleep(2)


async def test_try_get_node_with_name(
    autoscaling_docker: AutoscalingDocker, host_node: Node
):
    assert host_node.Description
    assert host_node.Description.Hostname

    received_node = await find_node_with_name(
        autoscaling_docker, host_node.Description.Hostname
    )
    assert received_node == host_node


async def test_try_get_node_with_name_fake(
    autoscaling_docker: AutoscalingDocker, fake_node: Node
):
    assert fake_node.Description
    assert fake_node.Description.Hostname

    received_node = await find_node_with_name(
        autoscaling_docker, fake_node.Description.Hostname
    )
    assert received_node is None


async def test_find_node_with_name_with_common_prefixed_nodes(
    autoscaling_docker: AutoscalingDocker,
    mocker: MockerFixture,
    create_fake_node: Callable[..., Node],
):
    common_prefix = "ip-10-0-1-"
    mocked_aiodocker = mocker.patch.object(autoscaling_docker, "nodes", autospec=True)
    mocked_aiodocker.list.return_value = [
        create_fake_node(
            Description=NodeDescription(Hostname=f"{common_prefix}{'1'*(i+1)}")
        )
        for i in range(3)
    ]
    needed_host_name = f"{common_prefix}11"
    found_node = await find_node_with_name(autoscaling_docker, needed_host_name)
    assert found_node
    assert found_node.Description
    assert found_node.Description.Hostname == needed_host_name


async def test_find_node_with_smaller_name_with_common_prefixed_nodes_returns_none(
    autoscaling_docker: AutoscalingDocker,
    mocker: MockerFixture,
    create_fake_node: Callable[..., Node],
):
    common_prefix = "ip-10-0-1-"
    mocked_aiodocker = mocker.patch.object(autoscaling_docker, "nodes", autospec=True)
    mocked_aiodocker.list.return_value = [
        create_fake_node(
            Description=NodeDescription(Hostname=f"{common_prefix}{'1'*(i+1)}")
        )
        for i in range(3)
    ]
    needed_host_name = f"{common_prefix}"
    found_node = await find_node_with_name(autoscaling_docker, needed_host_name)
    assert found_node is None


async def test_tag_node(
    autoscaling_docker: AutoscalingDocker, host_node: Node, faker: Faker
):
    assert host_node.Description
    assert host_node.Description.Hostname
    tags = faker.pydict(allowed_types=(str,))
    await tag_node(autoscaling_docker, host_node, tags=tags, available=False)
    updated_node = await find_node_with_name(
        autoscaling_docker, host_node.Description.Hostname
    )
    assert updated_node
    assert updated_node.Spec
    assert updated_node.Spec.Availability == Availability.drain
    assert updated_node.Spec.Labels == tags

    await tag_node(autoscaling_docker, updated_node, tags={}, available=True)
    updated_node = await find_node_with_name(
        autoscaling_docker, host_node.Description.Hostname
    )
    assert updated_node
    assert updated_node.Spec
    assert updated_node.Spec.Availability == Availability.active
    assert updated_node.Spec.Labels == {}


async def test_tag_node_out_of_sequence_error(
    autoscaling_docker: AutoscalingDocker, host_node: Node, faker: Faker
):
    assert host_node.Description
    assert host_node.Description.Hostname
    tags = faker.pydict(allowed_types=(str,))
    # this works
    updated_node = await tag_node(
        autoscaling_docker, host_node, tags=tags, available=False
    )
    assert updated_node
    assert host_node.Version
    assert host_node.Version.Index
    assert updated_node.Version
    assert updated_node.Version.Index
    assert host_node.Version.Index < updated_node.Version.Index

    # running the same call with the old node should not raise an out of sequence error
    updated_node2 = await tag_node(
        autoscaling_docker, host_node, tags=tags, available=True
    )
    assert updated_node2
    assert updated_node2.Version
    assert updated_node2.Version.Index
    assert updated_node2.Version.Index > updated_node.Version.Index


@pytest.mark.parametrize(
    "images, expected_cmd",
    [
        (
            ["nginx", "itisfoundation/simcore/services/dynamic/service:23.5.5"],
            'echo "services:\n  pre-pull-image-0:\n    image: nginx\n  pre-pull-image-1:\n    '
            'image: itisfoundation/simcore/services/dynamic/service:23.5.5\nversion: \'"3.8"\'\n"'
            " > /docker-pull.compose.yml"
            " && "
            'echo "#!/bin/sh\necho Pulling started at \\$(date)\ndocker compose --file=/docker-pull.compose.yml pull" > /docker-pull-script.sh'
            " && "
            "chmod +x /docker-pull-script.sh"
            " && "
            "./docker-pull-script.sh",
        ),
        (
            [],
            "",
        ),
    ],
)
def test_get_docker_pull_images_on_start_bash_command(
    images: list[DockerGenericTag], expected_cmd: str
):
    assert get_docker_pull_images_on_start_bash_command(images) == expected_cmd


@pytest.mark.parametrize(
    "interval, expected_cmd",
    [
        (
            datetime.timedelta(minutes=20),
            'echo "*/20 * * * * root /docker-pull-script.sh >> /var/log/docker-pull-cronjob.log 2>&1" >> /etc/crontab',
        ),
        (
            datetime.timedelta(seconds=20),
            'echo "*/1 * * * * root /docker-pull-script.sh >> /var/log/docker-pull-cronjob.log 2>&1" >> /etc/crontab',
        ),
        (
            datetime.timedelta(seconds=200),
            'echo "*/3 * * * * root /docker-pull-script.sh >> /var/log/docker-pull-cronjob.log 2>&1" >> /etc/crontab',
        ),
        (
            datetime.timedelta(days=3),
            'echo "*/4320 * * * * root /docker-pull-script.sh >> /var/log/docker-pull-cronjob.log 2>&1" >> /etc/crontab',
        ),
    ],
    ids=str,
)
def test_get_docker_pull_images_crontab(
    interval: datetime.timedelta, expected_cmd: str
):
    assert get_docker_pull_images_crontab(interval) == expected_cmd


def test__is_task_waiting_for_resources():
    task = Task(
        ID="dh85t6gj8nqto5ya6znc1qyh3",
        Version=ObjectVersion(Index=389913),
        CreatedAt="2023-11-13T22:24:34.831880582Z",
        UpdatedAt="2023-11-13T22:24:34.901288508Z",
        Name=None,
        Labels={},
        Spec=TaskSpec(
            PluginSpec=None,
            ContainerSpec=ContainerSpec(
                Image="itisfoundation/dynamic-sidecar:master-github-latest",
                Labels={
                    "io.simcore.runtime.cpu-limit": "5.0",
                    "io.simcore.runtime.memory-limit": "21474836480",
                    "io.simcore.runtime.node-id": "d512d1e7-fc47-4c1a-a18e-8a06b5cb389b",
                    "io.simcore.runtime.product-name": "s4l",
                    "io.simcore.runtime.project-id": "eae0f0f4-8272-11ee-b8a7-02420a000821",
                    "io.simcore.runtime.simcore-user-agent": "undefined",
                    "io.simcore.runtime.swarm-stack-name": "master-simcore",
                    "io.simcore.runtime.user-id": "6",
                },
                Command=None,
                Args=None,
                Hostname=None,
                Env=[
                    "DY_SIDECAR_NODE_ID=d512d1e7-fc47-4c1a-a18e-8a06b5cb389b",
                    "DY_SIDECAR_PATH_INPUTS=/home/smu/work/inputs",
                    "DY_SIDECAR_PATH_OUTPUTS=/home/smu/work/outputs",
                    "DY_SIDECAR_PROJECT_ID=eae0f0f4-8272-11ee-b8a7-02420a000821",
                    "DY_SIDECAR_RUN_ID=1699914274_756b14f9-e95e-4a5a-b2e5-6d2ff720a327",
                    "DY_SIDECAR_USER_SERVICES_HAVE_INTERNET_ACCESS=True",
                    "DY_SIDECAR_STATE_EXCLUDE=[]",
                    'DY_SIDECAR_CALLBACKS_MAPPING={"metrics": {"service": "s4l-core", "command": "/home/smu/s4l-core/docker/callbacks/on_metrics.sh", "timeout": 3.0}, "before_shutdown": [{"service": "s4l-core", "command": "/home/smu/s4l-core/docker/callbacks/on_shutdown.sh", "timeout": 180.0}], "inactivity": null}',
                    'DY_SIDECAR_STATE_PATHS=["/home/smu/work/workspace", "/.data/assets"]',
                    "DY_SIDECAR_USER_ID=6",
                    "DYNAMIC_SIDECAR_COMPOSE_NAMESPACE=dy-sidecar_d512d1e7-fc47-4c1a-a18e-8a06b5cb389b",
                    "DYNAMIC_SIDECAR_LOG_LEVEL=INFO",
                    "DY_SIDECAR_LOG_FORMAT_LOCAL_DEV_ENABLED=False",
                    "POSTGRES_DB=simcoredb",
                    "POSTGRES_ENDPOINT=osparcsim4life.ctq79nlxbu6q.us-east-1.rds.amazonaws.com:5432",
                    "POSTGRES_HOST=osparcsim4life.ctq79nlxbu6q.us-east-1.rds.amazonaws.com",
                    "POSTGRES_PASSWORD=bkT60vokPeADodsv",
                    "POSTGRES_PORT=5432",
                    "POSTGRES_USER=postgres",
                    "R_CLONE_PROVIDER=AWS",
                    "R_CLONE_OPTION_TRANSFERS=5",
                    "R_CLONE_OPTION_RETRIES=3",
                    "R_CLONE_OPTION_BUFFER_SIZE=0M",
                    "RABBIT_HOST=b-ba0107a7-f6aa-43b7-9801-8007dbd2b9a7.mq.us-east-1.amazonaws.com",
                    "RABBIT_PASSWORD=Tx4B2ERTvFZ4Q43vOm5LM3mcDTIi1fsk",
                    "RABBIT_PORT=5671",
                    "RABBIT_USER=scu",
                    "RABBIT_SECURE=True",
                    "REGISTRY_AUTH=True",
                    "REGISTRY_PATH=None",
                    "REGISTRY_PW=sjMyjGBymgdA8cFYApX99gd4",
                    "REGISTRY_SSL=True",
                    "REGISTRY_URL=registry.sim4life.io",
                    "REGISTRY_USER=admin",
                    "S3_ACCESS_KEY=AKIAUVO33BYP4DHOTJG6",
                    "S3_BUCKET_NAME=sim4life-simcore",
                    "S3_ENDPOINT=https://s3.amazonaws.com",
                    "S3_SECRET_KEY=h09sztj0vpdDyjzGEIR/70dHN4KhxxqtRTNpZStD",
                    "S3_SECURE=True",
                    "SC_BOOT_MODE=production",
                    "SSL_CERT_FILE=",
                    "SIMCORE_HOST_NAME=dy-sidecar_d512d1e7-fc47-4c1a-a18e-8a06b5cb389b",
                    "STORAGE_HOST=master_storage",
                    "STORAGE_PORT=8080",
                    "DY_SIDECAR_SERVICE_KEY=simcore/services/dynamic/sim4life-8-0-0-dy",
                    "DY_SIDECAR_SERVICE_VERSION=3.2.3",
                    "DY_SIDECAR_USER_PREFERENCES_PATH=/.data/Preferences",
                    "DY_SIDECAR_PRODUCT_NAME=s4l",
                    "NODE_PORTS_400_REQUEST_TIMEOUT_ATTEMPTS=3",
                    'FORWARD_ENV_S4L_CORE_HOSTNAME={"destination_containers": ["rt-web-dy"], "env_var": "%%container_name.s4l-core%%"}',
                    'FORWARD_ENV_S4L_STREAMING_HOSTNAME={"destination_containers": ["rt-web-dy"], "env_var": "%%container_name.s4l-stream%%"}',
                    'FORWARD_ENV_DISPLAY={"destination_containers": ["s4l-core"], "env_var": ":0"}',
                    'FORWARD_ENV_SYM_SERVER_HOSTNAME={"destination_containers": ["s4l-core"], "env_var": "%%container_name.sym-server%%"}',
                    'FORWARD_ENV_Z43_STREAMING_QOS_ZMQ_ADDRESS_SERVER={"destination_containers": ["s4l-core"], "env_var": "tcp://%%container_name.s4l-stream%%:8090"}',
                    'FORWARD_ENV_Z43_STREAMING_DATA_ZMQ_ADDRESS_SERVER={"destination_containers": ["s4l-core"], "env_var": "tcp://%%container_name.s4l-stream%%:8091"}',
                    'FORWARD_ENV_Z43_STREAMING_RTC_HANDLER_ADDRESS_SERVER={"destination_containers": ["s4l-core"], "env_var": "tcp://%%container_name.s4l-stream%%:8092"}',
                ],
                Dir=None,
                User=None,
                Groups=None,
                Privileges=None,
                TTY=None,
                OpenStdin=None,
                ReadOnly=None,
                Mounts=[
                    Mount(
                        Target="/var/run/docker.sock",
                        Source="/var/run/docker.sock",
                        Type=Type1.bind,
                        ReadOnly=None,
                        Consistency=None,
                        BindOptions=None,
                        VolumeOptions=None,
                        TmpfsOptions=None,
                    ),
                    Mount(
                        Target="/dy-volumes/shared-store",
                        Source="dyv_1699914274_756b14f9-e95e-4a5a-b2e5-6d2ff720a327_d512d1e7-fc47-4c1a-a18e-8a06b5cb389b_erots-derahs_",
                        Type=Type1.volume,
                        ReadOnly=None,
                        Consistency=None,
                        BindOptions=None,
                        VolumeOptions=VolumeOptions(
                            NoCopy=False,
                            Labels={
                                "node_uuid": "d512d1e7-fc47-4c1a-a18e-8a06b5cb389b",
                                "run_id": "1699914274_756b14f9-e95e-4a5a-b2e5-6d2ff720a327",
                                "source": "dyv_1699914274_756b14f9-e95e-4a5a-b2e5-6d2ff720a327_d512d1e7-fc47-4c1a-a18e-8a06b5cb389b_erots-derahs_",
                                "study_id": "eae0f0f4-8272-11ee-b8a7-02420a000821",
                                "swarm_stack_name": "master-simcore",
                                "user_id": "6",
                            },
                            DriverConfig=None,
                        ),
                        TmpfsOptions=None,
                    ),
                    Mount(
                        Target="/dy-volumes/home/smu/work/inputs",
                        Source="dyv_1699914274_756b14f9-e95e-4a5a-b2e5-6d2ff720a327_d512d1e7-fc47-4c1a-a18e-8a06b5cb389b_stupni_krow_ums_emoh_",
                        Type=Type1.volume,
                        ReadOnly=None,
                        Consistency=None,
                        BindOptions=None,
                        VolumeOptions=VolumeOptions(
                            NoCopy=False,
                            Labels={
                                "node_uuid": "d512d1e7-fc47-4c1a-a18e-8a06b5cb389b",
                                "run_id": "1699914274_756b14f9-e95e-4a5a-b2e5-6d2ff720a327",
                                "source": "dyv_1699914274_756b14f9-e95e-4a5a-b2e5-6d2ff720a327_d512d1e7-fc47-4c1a-a18e-8a06b5cb389b_stupni_krow_ums_emoh_",
                                "study_id": "eae0f0f4-8272-11ee-b8a7-02420a000821",
                                "swarm_stack_name": "master-simcore",
                                "user_id": "6",
                            },
                            DriverConfig=None,
                        ),
                        TmpfsOptions=None,
                    ),
                    Mount(
                        Target="/dy-volumes/home/smu/work/outputs",
                        Source="dyv_1699914274_756b14f9-e95e-4a5a-b2e5-6d2ff720a327_d512d1e7-fc47-4c1a-a18e-8a06b5cb389b_stuptuo_krow_ums_emoh_",
                        Type=Type1.volume,
                        ReadOnly=None,
                        Consistency=None,
                        BindOptions=None,
                        VolumeOptions=VolumeOptions(
                            NoCopy=False,
                            Labels={
                                "node_uuid": "d512d1e7-fc47-4c1a-a18e-8a06b5cb389b",
                                "run_id": "1699914274_756b14f9-e95e-4a5a-b2e5-6d2ff720a327",
                                "source": "dyv_1699914274_756b14f9-e95e-4a5a-b2e5-6d2ff720a327_d512d1e7-fc47-4c1a-a18e-8a06b5cb389b_stuptuo_krow_ums_emoh_",
                                "study_id": "eae0f0f4-8272-11ee-b8a7-02420a000821",
                                "swarm_stack_name": "master-simcore",
                                "user_id": "6",
                            },
                            DriverConfig=None,
                        ),
                        TmpfsOptions=None,
                    ),
                    Mount(
                        Target="/dy-volumes/home/smu/work/workspace",
                        Source="dyv_1699914274_756b14f9-e95e-4a5a-b2e5-6d2ff720a327_d512d1e7-fc47-4c1a-a18e-8a06b5cb389b_ecapskrow_krow_ums_emoh_",
                        Type=Type1.volume,
                        ReadOnly=None,
                        Consistency=None,
                        BindOptions=None,
                        VolumeOptions=VolumeOptions(
                            NoCopy=False,
                            Labels={
                                "node_uuid": "d512d1e7-fc47-4c1a-a18e-8a06b5cb389b",
                                "run_id": "1699914274_756b14f9-e95e-4a5a-b2e5-6d2ff720a327",
                                "source": "dyv_1699914274_756b14f9-e95e-4a5a-b2e5-6d2ff720a327_d512d1e7-fc47-4c1a-a18e-8a06b5cb389b_ecapskrow_krow_ums_emoh_",
                                "study_id": "eae0f0f4-8272-11ee-b8a7-02420a000821",
                                "swarm_stack_name": "master-simcore",
                                "user_id": "6",
                            },
                            DriverConfig=None,
                        ),
                        TmpfsOptions=None,
                    ),
                    Mount(
                        Target="/dy-volumes/.data/assets",
                        Source="dyv_1699914274_756b14f9-e95e-4a5a-b2e5-6d2ff720a327_d512d1e7-fc47-4c1a-a18e-8a06b5cb389b_stessa_atad._",
                        Type=Type1.volume,
                        ReadOnly=None,
                        Consistency=None,
                        BindOptions=None,
                        VolumeOptions=VolumeOptions(
                            NoCopy=False,
                            Labels={
                                "node_uuid": "d512d1e7-fc47-4c1a-a18e-8a06b5cb389b",
                                "run_id": "1699914274_756b14f9-e95e-4a5a-b2e5-6d2ff720a327",
                                "source": "dyv_1699914274_756b14f9-e95e-4a5a-b2e5-6d2ff720a327_d512d1e7-fc47-4c1a-a18e-8a06b5cb389b_stessa_atad._",
                                "study_id": "eae0f0f4-8272-11ee-b8a7-02420a000821",
                                "swarm_stack_name": "master-simcore",
                                "user_id": "6",
                            },
                            DriverConfig=None,
                        ),
                        TmpfsOptions=None,
                    ),
                    Mount(
                        Target="/dy-volumes/.data/Preferences",
                        Source="dyv_1699914274_756b14f9-e95e-4a5a-b2e5-6d2ff720a327_d512d1e7-fc47-4c1a-a18e-8a06b5cb389b_secnereferP_atad._",
                        Type=Type1.volume,
                        ReadOnly=None,
                        Consistency=None,
                        BindOptions=None,
                        VolumeOptions=VolumeOptions(
                            NoCopy=False,
                            Labels={
                                "node_uuid": "d512d1e7-fc47-4c1a-a18e-8a06b5cb389b",
                                "run_id": "1699914274_756b14f9-e95e-4a5a-b2e5-6d2ff720a327",
                                "source": "dyv_1699914274_756b14f9-e95e-4a5a-b2e5-6d2ff720a327_d512d1e7-fc47-4c1a-a18e-8a06b5cb389b_secnereferP_atad._",
                                "study_id": "eae0f0f4-8272-11ee-b8a7-02420a000821",
                                "swarm_stack_name": "master-simcore",
                                "user_id": "6",
                            },
                            DriverConfig=None,
                        ),
                        TmpfsOptions=None,
                    ),
                    Mount(
                        Target="/tmp/.X11-unix",
                        Source="/tmp/.X11-unix",
                        Type=Type1.bind,
                        ReadOnly=True,
                        Consistency=None,
                        BindOptions=None,
                        VolumeOptions=None,
                        TmpfsOptions=None,
                    ),
                ],
                StopSignal=None,
                StopGracePeriod=None,
                HealthCheck=None,
                Hosts=None,
                DNSConfig=None,
                Secrets=None,
                Configs=None,
                Isolation=Isolation.default,
                Init=True,
                Sysctls=None,
                CapabilityAdd=["CAP_LINUX_IMMUTABLE"],
                CapabilityDrop=None,
                Ulimits=None,
            ),
            NetworkAttachmentSpec=None,
            Resources=Resources1(
                Limits=Limit(NanoCPUs=5000000000, MemoryBytes=21474836480, Pids=0),
                Reservations=ResourceObject(
                    NanoCPUs=5000000000,
                    MemoryBytes=21474836480,
                    GenericResources=GenericResources(
                        __root__=[
                            GenericResource(
                                NamedResourceSpec=None,
                                DiscreteResourceSpec=DiscreteResourceSpec(
                                    Kind="VRAM", Value=1
                                ),
                            )
                        ]
                    ),
                ),
            ),
            RestartPolicy=RestartPolicy1(
                Condition=Condition.on_failure,
                Delay=5000000000,
                MaxAttempts=0,
                Window=0,
            ),
            Placement=Placement(
                Constraints=[
                    "node.platform.os == linux",
                    "node.labels.io.simcore.s4l-autoscaled-node==true",
                ],
                Preferences=None,
                MaxReplicas=0,
                Platforms=None,
            ),
            ForceUpdate=0,
            Runtime=None,
            Networks=None,
            LogDriver=None,
        ),
        ServiceID="yt21esx3jjwul1uuq6qlj8op8",
        Slot=1,
        NodeID=None,
        AssignedGenericResources=None,
        Status=Status1(
            Timestamp="2023-11-13T22:24:34.90121361Z",
            State=TaskState.pending,
            Message="pending task scheduling",
            Err="no suitable node (insufficient resources on 8 nodes; scheduling constraints not satisfied on 1 node)",
            ContainerStatus=None,
        ),
        DesiredState=TaskState.running,
        JobIteration=None,
    )
    assert _is_task_waiting_for_resources(task) == True
