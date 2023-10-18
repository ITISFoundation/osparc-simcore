""" Free helper functions for docker API

"""

import asyncio
import collections
import datetime
import logging
import re
from contextlib import suppress
from pathlib import Path
from typing import Final, cast

import yaml
from models_library.docker import DockerGenericTag, DockerLabelKey
from models_library.generated_models.docker_rest_api import (
    Node,
    NodeState,
    Service,
    Task,
    TaskState,
)
from pydantic import ByteSize, parse_obj_as
from servicelib.docker_utils import to_datetime
from servicelib.logging_utils import log_context
from servicelib.utils import logged_gather
from settings_library.docker_registry import RegistrySettings

from ..core.settings import ApplicationSettings
from ..models import Resources
from ..modules.docker import AutoscalingDocker

logger = logging.getLogger(__name__)
_NANO_CPU: Final[float] = 10**9

_TASK_STATUS_WITH_ASSIGNED_RESOURCES: Final[tuple[TaskState, ...]] = (
    TaskState.assigned,
    TaskState.accepted,
    TaskState.preparing,
    TaskState.starting,
    TaskState.running,
)

_DISALLOWED_DOCKER_PLACEMENT_CONSTRAINTS: Final[list[str]] = [
    "node.id",
    "node.hostname",
    "node.role",
]

_PENDING_DOCKER_TASK_MESSAGE: Final[str] = "pending task scheduling"
_INSUFFICIENT_RESOURCES_DOCKER_TASK_ERR: Final[str] = "insufficient resources on"


async def get_monitored_nodes(
    docker_client: AutoscalingDocker, node_labels: list[DockerLabelKey]
) -> list[Node]:
    return parse_obj_as(
        list[Node],
        await docker_client.nodes.list(
            filters={"node.label": [f"{label}=true" for label in node_labels]}
        ),
    )


async def remove_nodes(
    docker_client: AutoscalingDocker, nodes: list[Node], force: bool = False
) -> list[Node]:
    """removes docker nodes that are in the down state (unless force is used and they will be forcibly removed)"""

    def _check_if_node_is_removable(node: Node) -> bool:
        if node.Status and node.Status.State:
            return node.Status.State in [
                NodeState.down,
                NodeState.disconnected,
                NodeState.unknown,
            ]
        logger.warning(
            "%s has no Status/State! This is unexpected and shall be checked",
            f"{node=}",
        )
        # we do not remove a node that has a weird state, let it be done by someone smarter.
        return False

    nodes_that_need_removal = [
        n for n in nodes if (force is True) or _check_if_node_is_removable(n)
    ]
    for node in nodes_that_need_removal:
        assert node.ID  # nosec
        with log_context(logger, logging.INFO, msg=f"remove {node.ID=}"):
            await docker_client.nodes.remove(node_id=node.ID, force=force)
    return nodes_that_need_removal


def _is_task_waiting_for_resources(task: Task) -> bool:
    # NOTE: https://docs.docker.com/engine/swarm/how-swarm-mode-works/swarm-task-states/
    if (
        not task.Status
        or not task.Status.State
        or not task.Status.Message
        or not task.Status.Err
    ):
        return False
    return (
        task.Status.State == TaskState.pending
        and task.Status.Message == _PENDING_DOCKER_TASK_MESSAGE
        and _INSUFFICIENT_RESOURCES_DOCKER_TASK_ERR in task.Status.Err
    )


async def _associated_service_has_no_node_placement_contraints(
    docker_client: AutoscalingDocker, task: Task
) -> bool:
    assert task.ServiceID  # nosec
    service_inspect = parse_obj_as(
        Service, await docker_client.services.inspect(task.ServiceID)
    )
    assert service_inspect.Spec  # nosec
    assert service_inspect.Spec.TaskTemplate  # nosec

    if (
        not service_inspect.Spec.TaskTemplate.Placement
        or not service_inspect.Spec.TaskTemplate.Placement.Constraints
    ):
        return True
    # parse the placement contraints
    service_placement_constraints = (
        service_inspect.Spec.TaskTemplate.Placement.Constraints
    )
    for constraint in service_placement_constraints:
        # is of type node.id==alskjladskjs or node.hostname==thiscomputerhostname or node.role==manager, sometimes with spaces...
        if any(
            constraint.startswith(c) for c in _DISALLOWED_DOCKER_PLACEMENT_CONSTRAINTS
        ):
            return False
    return True


def _by_created_dt(task: Task) -> datetime.datetime:
    # NOTE: SAFE implementation to extract task.CreatedAt as datetime for comparison
    if task.CreatedAt:
        with suppress(ValueError):
            created_at = to_datetime(task.CreatedAt)
            created_at_utc: datetime.datetime = created_at.replace(
                tzinfo=datetime.timezone.utc
            )
            return created_at_utc
    return datetime.datetime.now(datetime.timezone.utc)


async def pending_service_tasks_with_insufficient_resources(
    docker_client: AutoscalingDocker,
    service_labels: list[DockerLabelKey],
) -> list[Task]:
    """
    Returns the docker service tasks that are currently pending due to missing resources.

    Tasks pending with insufficient resources are
    - pending
    - have an error message with "insufficient resources"
    - are not scheduled on any node
    """
    tasks = parse_obj_as(
        list[Task],
        await docker_client.tasks.list(
            filters={
                "desired-state": "running",
                "label": service_labels,
            }
        ),
    )

    sorted_tasks = sorted(tasks, key=_by_created_dt)

    return [
        task
        for task in sorted_tasks
        if (
            _is_task_waiting_for_resources(task)
            and await _associated_service_has_no_node_placement_contraints(
                docker_client, task
            )
        )
    ]


def get_node_total_resources(node: Node) -> Resources:
    assert node.Description  # nosec
    assert node.Description.Resources  # nosec
    assert node.Description.Resources.NanoCPUs  # nosec
    assert node.Description.Resources.MemoryBytes  # nosec
    return Resources(
        cpus=node.Description.Resources.NanoCPUs / _NANO_CPU,
        ram=ByteSize(node.Description.Resources.MemoryBytes),
    )


async def compute_cluster_total_resources(nodes: list[Node]) -> Resources:
    """
    Returns the nodes total resources.
    """
    cluster_resources_counter = collections.Counter({"ram": 0, "cpus": 0})
    for node in nodes:
        assert node.Description  # nosec
        assert node.Description.Resources  # nosec
        assert node.Description.Resources.NanoCPUs  # nosec
        cluster_resources_counter.update(
            {
                "ram": node.Description.Resources.MemoryBytes,
                "cpus": node.Description.Resources.NanoCPUs / _NANO_CPU,
            }
        )

    return Resources.parse_obj(dict(cluster_resources_counter))


def get_max_resources_from_docker_task(task: Task) -> Resources:
    """returns the highest values for resources based on both docker reservations and limits"""
    assert task.Spec  # nosec
    if task.Spec.Resources:
        return Resources(
            cpus=max(
                (
                    task.Spec.Resources.Reservations
                    and task.Spec.Resources.Reservations.NanoCPUs
                    or 0
                ),
                (
                    task.Spec.Resources.Limits
                    and task.Spec.Resources.Limits.NanoCPUs
                    or 0
                ),
            )
            / _NANO_CPU,
            ram=parse_obj_as(
                ByteSize,
                max(
                    task.Spec.Resources.Reservations
                    and task.Spec.Resources.Reservations.MemoryBytes
                    or 0,
                    task.Spec.Resources.Limits
                    and task.Spec.Resources.Limits.MemoryBytes
                    or 0,
                ),
            ),
        )
    return Resources(cpus=0, ram=ByteSize(0))


def compute_tasks_needed_resources(tasks: list[Task]) -> Resources:
    total = Resources.create_as_empty()
    for t in tasks:
        total += get_max_resources_from_docker_task(t)
    return total


async def compute_node_used_resources(
    docker_client: AutoscalingDocker,
    node: Node,
    service_labels: list[DockerLabelKey] | None = None,
) -> Resources:
    cluster_resources_counter = collections.Counter({"ram": 0, "cpus": 0})
    task_filters = {"node": node.ID}
    if service_labels:
        task_filters |= {"label": service_labels}
    all_tasks_on_node = parse_obj_as(
        list[Task],
        await docker_client.tasks.list(filters=task_filters),
    )
    for task in all_tasks_on_node:
        assert task.Status  # nosec
        if (
            task.Status.State in _TASK_STATUS_WITH_ASSIGNED_RESOURCES
            and task.Spec
            and task.Spec.Resources
            and task.Spec.Resources.Reservations
        ):
            task_reservations = task.Spec.Resources.Reservations.dict(exclude_none=True)
            cluster_resources_counter.update(
                {
                    "ram": task_reservations.get("MemoryBytes", 0),
                    "cpus": task_reservations.get("NanoCPUs", 0) / _NANO_CPU,
                }
            )
    return Resources.parse_obj(dict(cluster_resources_counter))


async def compute_cluster_used_resources(
    docker_client: AutoscalingDocker, nodes: list[Node]
) -> Resources:
    """Returns the total amount of resources (reservations) used on each of the given nodes"""
    list_of_used_resources = await logged_gather(
        *(compute_node_used_resources(docker_client, node) for node in nodes)
    )
    counter = collections.Counter({k: 0 for k in Resources.__fields__})
    for result in list_of_used_resources:
        counter.update(result.dict())

    return Resources.parse_obj(dict(counter))


_COMMAND_TIMEOUT_S = 10
_DOCKER_SWARM_JOIN_RE = r"(?P<command>docker swarm join)\s+(?P<token>--token\s+[\w-]+)\s+(?P<address>[0-9\.:]+)"
_DOCKER_SWARM_JOIN_PATTERN = re.compile(_DOCKER_SWARM_JOIN_RE)


async def get_docker_swarm_join_bash_command() -> str:
    """this assumes we are on a manager node"""
    command = ["docker", "swarm", "join-token", "worker"]
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    await asyncio.wait_for(process.wait(), timeout=_COMMAND_TIMEOUT_S)
    assert process.returncode is not None  # nosec
    if process.returncode > 0:
        msg = f"unexpected error running '{' '.join(command)}': {stderr.decode()}"
        raise RuntimeError(msg)
    decoded_stdout = stdout.decode()
    if match := re.search(_DOCKER_SWARM_JOIN_PATTERN, decoded_stdout):
        capture = match.groupdict()
        return f"{capture['command']} --availability=drain {capture['token']} {capture['address']}"
    msg = f"expected docker '{_DOCKER_SWARM_JOIN_RE}' command not found: received {decoded_stdout}!"
    raise RuntimeError(msg)


def get_docker_login_on_start_bash_command(registry_settings: RegistrySettings) -> str:
    return " ".join(
        [
            "echo",
            f'"{registry_settings.REGISTRY_PW.get_secret_value()}"',
            "|",
            "docker",
            "login",
            "--username",
            registry_settings.REGISTRY_USER,
            "--password-stdin",
            registry_settings.resolved_registry_url,
        ]
    )


_DOCKER_COMPOSE_CMD: Final[str] = "docker compose"
_PRE_PULL_COMPOSE_PATH: Final[Path] = Path("/docker-pull.compose.yml")
_DOCKER_COMPOSE_PULL_SCRIPT_PATH: Final[Path] = Path("/docker-pull-script.sh")
_CRONJOB_LOGS_PATH: Final[Path] = Path("/var/log/docker-pull-cronjob.log")


def get_docker_pull_images_on_start_bash_command(
    docker_tags: list[DockerGenericTag],
) -> str:
    if not docker_tags:
        return ""

    compose = {
        "version": '"3.8"',
        "services": {
            f"pre-pull-image-{n}": {"image": image_tag}
            for n, image_tag in enumerate(docker_tags)
        },
    }
    compose_yaml = yaml.safe_dump(compose)
    write_compose_file_cmd = " ".join(
        ["echo", f'"{compose_yaml}"', ">", f"{_PRE_PULL_COMPOSE_PATH}"]
    )
    write_docker_compose_pull_script_cmd = " ".join(
        [
            "echo",
            f'"#!/bin/sh\necho Pulling started at \\$(date)\n{_DOCKER_COMPOSE_CMD} --file={_PRE_PULL_COMPOSE_PATH} pull"',
            ">",
            f"{_DOCKER_COMPOSE_PULL_SCRIPT_PATH}",
        ]
    )
    make_docker_compose_script_executable = " ".join(
        ["chmod", "+x", f"{_DOCKER_COMPOSE_PULL_SCRIPT_PATH}"]
    )
    docker_compose_pull_cmd = " ".join([f".{_DOCKER_COMPOSE_PULL_SCRIPT_PATH}"])
    return " && ".join(
        [
            write_compose_file_cmd,
            write_docker_compose_pull_script_cmd,
            make_docker_compose_script_executable,
            docker_compose_pull_cmd,
        ]
    )


def get_docker_pull_images_crontab(interval: datetime.timedelta) -> str:
    # check the interval is within 1 < 60 minutes
    checked_interval = round(interval.total_seconds() / 60)

    crontab_entry = " ".join(
        [
            "echo",
            f'"*/{checked_interval or 1} * * * * root',
            f"{_DOCKER_COMPOSE_PULL_SCRIPT_PATH}",
            f'>> {_CRONJOB_LOGS_PATH} 2>&1"',
            ">>",
            "/etc/crontab",
        ]
    )
    return " && ".join([crontab_entry])


async def find_node_with_name(
    docker_client: AutoscalingDocker, name: str
) -> Node | None:
    list_of_nodes = await docker_client.nodes.list(filters={"name": name})
    if not list_of_nodes:
        return None
    # note that there might be several nodes with a common_prefixed name. so now we want exact matching
    list_of_nodes = parse_obj_as(list[Node], list_of_nodes)
    for node in list_of_nodes:
        assert node.Description  # nosec
        if node.Description.Hostname == name:
            return node

    return None


async def tag_node(
    docker_client: AutoscalingDocker,
    node: Node,
    *,
    tags: dict[DockerLabelKey, str],
    available: bool,
) -> Node:
    with log_context(
        logger, logging.DEBUG, msg=f"tagging {node.ID=} with {tags=} and {available=}"
    ):
        assert node.ID  # nosec

        latest_version_node = parse_obj_as(
            Node, await docker_client.nodes.inspect(node_id=node.ID)
        )
        assert latest_version_node.Version  # nosec
        assert latest_version_node.Version.Index  # nosec
        assert latest_version_node.Spec  # nosec
        assert latest_version_node.Spec.Role  # nosec

        # updating now should work nicely
        await docker_client.nodes.update(
            node_id=node.ID,
            version=latest_version_node.Version.Index,
            spec={
                "Availability": "active" if available else "drain",
                "Labels": tags,
                "Role": latest_version_node.Spec.Role.value,
            },
        )
        return parse_obj_as(Node, await docker_client.nodes.inspect(node_id=node.ID))


async def set_node_availability(
    docker_client: AutoscalingDocker, node: Node, *, available: bool
) -> Node:
    assert node.Spec  # nosec
    return await tag_node(
        docker_client,
        node,
        tags=cast(dict[DockerLabelKey, str], node.Spec.Labels),
        available=available,
    )


def get_docker_tags(app_settings: ApplicationSettings) -> dict[DockerLabelKey, str]:
    assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec
    return {
        tag_key: "true"
        for tag_key in app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS
    } | {
        tag_key: "true"
        for tag_key in app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NEW_NODES_LABELS
    }
