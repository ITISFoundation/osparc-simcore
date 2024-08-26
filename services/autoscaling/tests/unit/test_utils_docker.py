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
import arrow
import pytest
from aws_library.ec2 import EC2InstanceData, Resources
from deepdiff import DeepDiff
from faker import Faker
from models_library.docker import (
    DOCKER_TASK_EC2_INSTANCE_TYPE_PLACEMENT_CONSTRAINT_KEY,
    DockerGenericTag,
    DockerLabelKey,
)
from models_library.generated_models.docker_rest_api import (
    Availability,
    NodeDescription,
    NodeSpec,
    NodeState,
    NodeStatus,
    Service,
    Task,
)
from pydantic import ByteSize, parse_obj_as
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from servicelib.docker_utils import to_datetime
from settings_library.docker_registry import RegistrySettings
from simcore_service_autoscaling.core.settings import ApplicationSettings
from simcore_service_autoscaling.modules.docker import AutoscalingDocker
from simcore_service_autoscaling.utils.utils_docker import (
    _OSPARC_NODE_EMPTY_DATETIME_LABEL_KEY,
    _OSPARC_NODE_TERMINATION_PROCESS_LABEL_KEY,
    _OSPARC_SERVICE_READY_LABEL_KEY,
    _OSPARC_SERVICES_READY_DATETIME_LABEL_KEY,
    Node,
    _by_created_dt,
    attach_node,
    compute_cluster_total_resources,
    compute_cluster_used_resources,
    compute_node_used_resources,
    compute_tasks_needed_resources,
    find_node_with_name,
    get_docker_login_on_start_bash_command,
    get_docker_pull_images_crontab,
    get_docker_pull_images_on_start_bash_command,
    get_docker_swarm_join_bash_command,
    get_max_resources_from_docker_task,
    get_monitored_nodes,
    get_new_node_docker_tags,
    get_node_empty_since,
    get_node_last_readyness_update,
    get_node_termination_started_since,
    get_node_total_resources,
    get_task_instance_restriction,
    get_worker_nodes,
    is_node_osparc_ready,
    is_node_ready_and_available,
    pending_service_tasks_with_insufficient_resources,
    remove_nodes,
    set_node_availability,
    set_node_begin_termination_process,
    set_node_found_empty,
    set_node_osparc_ready,
    tag_node,
)
from types_aiobotocore_ec2.literals import InstanceTypeType


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
    await create_node_labels(
        [
            *labels,
            _OSPARC_SERVICE_READY_LABEL_KEY,
            _OSPARC_SERVICES_READY_DATETIME_LABEL_KEY,
        ]
    )
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
        exclude_paths=[
            "UpdatedAt",
            "Version",
            "root['Status']['Err']",
            "root['Status']['Timestamp']",
        ],
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
    await create_service(
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
        exclude_paths=[
            "UpdatedAt",
            "Version",
            "root['Status']['Err']",
            "root['Status']['Timestamp']",
        ],
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


@pytest.mark.parametrize(
    "placement_constraints, expected_instance_type",
    [
        (None, None),
        (["blahblah==true", "notsoblahblah!=true"], None),
        (["blahblah==true", "notsoblahblah!=true", "node.labels.blahblah==true"], None),
        (
            [
                "blahblah==true",
                "notsoblahblah!=true",
                f"node.labels.{DOCKER_TASK_EC2_INSTANCE_TYPE_PLACEMENT_CONSTRAINT_KEY}==true",
            ],
            None,
        ),
        (
            [
                "blahblah==true",
                "notsoblahblah!=true",
                f"node.labels.{DOCKER_TASK_EC2_INSTANCE_TYPE_PLACEMENT_CONSTRAINT_KEY}==t3.medium",
            ],
            "t3.medium",
        ),
    ],
)
async def test_get_task_instance_restriction(
    autoscaling_docker: AutoscalingDocker,
    host_node: Node,
    create_service: Callable[
        [dict[str, Any], dict[DockerLabelKey, str] | None, str, list[str] | None],
        Awaitable[Service],
    ],
    task_template: dict[str, Any],
    create_task_reservations: Callable[[int, int], dict[str, Any]],
    faker: Faker,
    placement_constraints: list[str] | None,
    expected_instance_type: InstanceTypeType | None,
):
    # this one has no instance restriction
    service = await create_service(
        task_template,
        None,
        "pending" if placement_constraints else "running",
        placement_constraints,
    )
    assert service.Spec
    service_tasks = parse_obj_as(
        list[Task],
        await autoscaling_docker.tasks.list(filters={"service": service.Spec.Name}),
    )
    instance_type_or_none = await get_task_instance_restriction(
        autoscaling_docker, service_tasks[0]
    )
    assert instance_type_or_none == expected_instance_type


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
        assert s.Spec
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
    await create_service(task_template, {}, "running")
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
        autoscaling_docker, host_node, service_labels=[DockerLabelKey(faker.pystr())]
    )
    assert node_used_resources == Resources(cpus=0, ram=ByteSize(0))
    # 4. if we look for services with 1 correct label, they should then become visible again
    node_used_resources = await compute_node_used_resources(
        autoscaling_docker,
        host_node,
        service_labels=[random.choice(list(service_labels.keys()))],  # noqa: S311
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


def test_get_docker_login_on_start_bash_command():
    registry_settings = RegistrySettings(
        **RegistrySettings.Config.schema_extra["examples"][0]
    )
    returned_command = get_docker_login_on_start_bash_command(registry_settings)
    assert (
        f'echo "{registry_settings.REGISTRY_PW.get_secret_value()}" | docker login --username {registry_settings.REGISTRY_USER} --password-stdin {registry_settings.resolved_registry_url}'
        == returned_command
    )


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


async def test_set_node_availability(
    autoscaling_docker: AutoscalingDocker, host_node: Node, faker: Faker
):
    assert is_node_ready_and_available(host_node, availability=Availability.active)
    updated_node = await set_node_availability(
        autoscaling_docker, host_node, available=False
    )
    assert is_node_ready_and_available(updated_node, availability=Availability.drain)
    updated_node = await set_node_availability(
        autoscaling_docker, host_node, available=True
    )
    assert is_node_ready_and_available(updated_node, availability=Availability.active)


def test_get_new_node_docker_tags(
    disabled_rabbitmq: None,
    disabled_ec2: None,
    disabled_ssm: None,
    mocked_redis_server: None,
    enabled_dynamic_mode: EnvVarsDict,
    disable_dynamic_service_background_task: None,
    app_settings: ApplicationSettings,
    fake_ec2_instance_data: Callable[..., EC2InstanceData],
):
    ec2_instance_data = fake_ec2_instance_data()
    node_docker_tags = get_new_node_docker_tags(app_settings, ec2_instance_data)
    assert node_docker_tags
    assert DOCKER_TASK_EC2_INSTANCE_TYPE_PLACEMENT_CONSTRAINT_KEY in node_docker_tags
    assert app_settings.AUTOSCALING_NODES_MONITORING
    for (
        tag_key
    ) in app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS:
        assert tag_key in node_docker_tags
    for (
        tag_key
    ) in app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NEW_NODES_LABELS:
        assert tag_key in node_docker_tags

    all_keys = [
        DOCKER_TASK_EC2_INSTANCE_TYPE_PLACEMENT_CONSTRAINT_KEY,
        *app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS,
        *app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NEW_NODES_LABELS,
    ]
    for tag_key in node_docker_tags:
        assert tag_key in all_keys


@pytest.mark.parametrize(
    "images, expected_cmd",
    [
        (
            ["nginx", "itisfoundation/simcore/services/dynamic/service:23.5.5"],
            'echo "services:\n  nginx:\n    image: nginx\n  service-23.5.5:\n    '
            'image: itisfoundation/simcore/services/dynamic/service:23.5.5\n"'
            " > /docker-pull.compose.yml"
            " && "
            'echo "#!/bin/sh\necho Pulling started at \\$(date)\ndocker compose --project-name=autoscaleprepull --file=/docker-pull.compose.yml pull --ignore-pull-failures" > /docker-pull-script.sh'
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


def test_is_node_ready_and_available(create_fake_node: Callable[..., Node]):
    # check not ready state return false
    for node_status in [
        NodeStatus(State=s, Message=None, Addr=None)
        for s in NodeState
        if s is not NodeState.ready
    ]:
        fake_node = create_fake_node(Status=node_status)
        assert not is_node_ready_and_available(
            fake_node, availability=Availability.drain
        )

    node_ready_status = NodeStatus(State=NodeState.ready, Message=None, Addr=None)
    fake_drained_node = create_fake_node(
        Status=node_ready_status,
        Spec=NodeSpec(
            Name=None,
            Labels=None,
            Role=None,
            Availability=Availability.drain,
        ),
    )
    assert is_node_ready_and_available(
        fake_drained_node, availability=Availability.drain
    )
    assert not is_node_ready_and_available(
        fake_drained_node, availability=Availability.active
    )
    assert not is_node_ready_and_available(
        fake_drained_node, availability=Availability.pause
    )


def test_is_node_osparc_ready(create_fake_node: Callable[..., Node], faker: Faker):
    fake_node = create_fake_node()
    assert fake_node.Spec
    assert fake_node.Spec.Availability is Availability.drain
    # no labels, not ready and drained
    assert not is_node_osparc_ready(fake_node)
    # no labels, not ready, but active
    fake_node.Spec.Availability = Availability.active
    assert not is_node_osparc_ready(fake_node)
    # no labels, ready and active
    fake_node.Status = NodeStatus(State=NodeState.ready, Message=None, Addr=None)
    assert not is_node_osparc_ready(fake_node)
    # add some random labels
    assert fake_node.Spec
    fake_node.Spec.Labels = faker.pydict(allowed_types=(str,))
    assert not is_node_osparc_ready(fake_node)
    # add the expected label
    fake_node.Spec.Labels[_OSPARC_SERVICE_READY_LABEL_KEY] = "false"
    assert not is_node_osparc_ready(fake_node)
    # make it ready
    fake_node.Spec.Labels[_OSPARC_SERVICE_READY_LABEL_KEY] = "true"
    assert is_node_osparc_ready(fake_node)


async def test_set_node_osparc_ready(
    disabled_rabbitmq: None,
    disabled_ec2: None,
    disabled_ssm: None,
    mocked_redis_server: None,
    enabled_dynamic_mode: EnvVarsDict,
    disable_dynamic_service_background_task: None,
    app_settings: ApplicationSettings,
    autoscaling_docker: AutoscalingDocker,
    host_node: Node,
):
    # initial state
    assert is_node_ready_and_available(host_node, availability=Availability.active)
    host_node_last_readyness_update = get_node_last_readyness_update(host_node)
    assert host_node_last_readyness_update
    # set the node to drain
    updated_node = await set_node_availability(
        autoscaling_docker, host_node, available=False
    )
    assert is_node_ready_and_available(updated_node, availability=Availability.drain)
    # the node is also not osparc ready
    assert not is_node_osparc_ready(updated_node)
    # the node readyness label was not updated here
    updated_last_readyness = get_node_last_readyness_update(updated_node)
    assert updated_last_readyness == host_node_last_readyness_update

    # this implicitely make the node active as well
    updated_node = await set_node_osparc_ready(
        app_settings, autoscaling_docker, host_node, ready=True
    )
    assert is_node_ready_and_available(updated_node, availability=Availability.active)
    assert is_node_osparc_ready(updated_node)
    updated_last_readyness = get_node_last_readyness_update(updated_node)
    assert updated_last_readyness > host_node_last_readyness_update
    # make it not osparc ready
    updated_node = await set_node_osparc_ready(
        app_settings, autoscaling_docker, host_node, ready=False
    )
    assert not is_node_osparc_ready(updated_node)
    assert is_node_ready_and_available(updated_node, availability=Availability.drain)
    assert get_node_last_readyness_update(updated_node) > updated_last_readyness


async def test_set_node_found_empty(
    disabled_rabbitmq: None,
    disabled_ec2: None,
    disabled_ssm: None,
    mocked_redis_server: None,
    enabled_dynamic_mode: EnvVarsDict,
    disable_dynamic_service_background_task: None,
    host_node: Node,
    autoscaling_docker: AutoscalingDocker,
):
    # initial state
    assert is_node_ready_and_available(host_node, availability=Availability.active)
    assert host_node.Spec
    assert host_node.Spec.Labels
    assert _OSPARC_NODE_EMPTY_DATETIME_LABEL_KEY not in host_node.Spec.Labels

    # the date does not exist as nothing was done
    node_empty_since = await get_node_empty_since(host_node)
    assert node_empty_since is None

    # now we set it to empty
    updated_node = await set_node_found_empty(autoscaling_docker, host_node, empty=True)
    assert updated_node.Spec
    assert updated_node.Spec.Labels
    assert _OSPARC_NODE_EMPTY_DATETIME_LABEL_KEY in updated_node.Spec.Labels

    # we can get that empty date back
    node_empty_since = await get_node_empty_since(updated_node)
    assert node_empty_since is not None
    assert node_empty_since < arrow.utcnow().datetime

    # now we remove the empty label
    updated_node = await set_node_found_empty(
        autoscaling_docker, host_node, empty=False
    )
    assert updated_node.Spec
    assert updated_node.Spec.Labels
    assert _OSPARC_NODE_EMPTY_DATETIME_LABEL_KEY not in updated_node.Spec.Labels

    # we can't get a date anymore
    node_empty_since = await get_node_empty_since(updated_node)
    assert node_empty_since is None


async def test_set_node_begin_termination_process(
    disabled_rabbitmq: None,
    disabled_ec2: None,
    disabled_ssm: None,
    mocked_redis_server: None,
    enabled_dynamic_mode: EnvVarsDict,
    disable_dynamic_service_background_task: None,
    host_node: Node,
    autoscaling_docker: AutoscalingDocker,
):
    # initial state
    assert is_node_ready_and_available(host_node, availability=Availability.active)
    assert host_node.Spec
    assert host_node.Spec.Labels
    assert _OSPARC_NODE_TERMINATION_PROCESS_LABEL_KEY not in host_node.Spec.Labels

    # the termination was not started, therefore no date
    assert get_node_termination_started_since(host_node) is None

    updated_node = await set_node_begin_termination_process(
        autoscaling_docker, host_node
    )
    assert updated_node.Spec
    assert updated_node.Spec.Labels
    assert _OSPARC_NODE_TERMINATION_PROCESS_LABEL_KEY in updated_node.Spec.Labels

    await asyncio.sleep(1)

    returned_termination_started_at = get_node_termination_started_since(updated_node)
    assert returned_termination_started_at is not None
    assert arrow.utcnow().datetime > returned_termination_started_at


async def test_attach_node(
    disabled_rabbitmq: None,
    disabled_ec2: None,
    disabled_ssm: None,
    mocked_redis_server: None,
    enabled_dynamic_mode: EnvVarsDict,
    disable_dynamic_service_background_task: None,
    app_settings: ApplicationSettings,
    autoscaling_docker: AutoscalingDocker,
    host_node: Node,
    faker: Faker,
):
    # initial state
    assert is_node_ready_and_available(host_node, availability=Availability.active)
    # set the node to drain
    updated_node = await set_node_availability(
        autoscaling_docker, host_node, available=False
    )
    assert is_node_ready_and_available(updated_node, availability=Availability.drain)
    # now attach the node
    updated_node = await attach_node(
        app_settings,
        autoscaling_docker,
        updated_node,
        tags=faker.pydict(allowed_types=(str,)),
    )
    # expected the node to be active
    assert is_node_ready_and_available(host_node, availability=Availability.active)
    # but not osparc ready
    assert not is_node_osparc_ready(updated_node)
