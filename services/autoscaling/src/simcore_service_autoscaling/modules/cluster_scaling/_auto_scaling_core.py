import asyncio
import collections
import dataclasses
import datetime
import functools
import itertools
import logging
from typing import Final, cast

import arrow
from aws_library.ec2 import (
    EC2InstanceConfig,
    EC2InstanceData,
    EC2InstanceType,
    EC2Tags,
    Resources,
)
from aws_library.ec2._errors import (
    EC2AccessError,
    EC2InsufficientCapacityError,
    EC2TooManyInstancesError,
)
from aws_library.ec2._models import AWSTagKey
from aws_library.ssm._errors import SSMAccessError
from common_library.logging.logging_errors import create_troubleshooting_log_kwargs
from fastapi import FastAPI
from models_library.docker import DockerLabelKey
from models_library.generated_models.docker_rest_api import Node
from models_library.rabbitmq_messages import ProgressType
from servicelib.logging_utils import log_catch, log_context
from servicelib.utils import limited_gather
from servicelib.utils_formatting import timedelta_as_minute_second
from types_aiobotocore_ec2.literals import InstanceTypeType

from ...constants import (
    DOCKER_JOIN_COMMAND_EC2_TAG_KEY,
    DOCKER_JOIN_COMMAND_NAME,
    DOCKER_PULL_COMMAND,
    MACHINE_PULLING_COMMAND_ID_EC2_TAG_KEY,
    MACHINE_PULLING_EC2_TAG_KEY,
    PREPULL_COMMAND_NAME,
)
from ...core.errors import (
    Ec2InvalidDnsNameError,
    Ec2TagDeserializationError,
    TaskBestFittingInstanceNotFoundError,
    TaskRequirementsAboveRequiredEC2InstanceTypeError,
    TaskRequiresUnauthorizedEC2InstanceTypeError,
)
from ...core.settings import ApplicationSettings, get_application_settings
from ...models import (
    AssignedTasksToInstanceType,
    AssociatedInstance,
    Cluster,
    NonAssociatedInstance,
)
from ...utils import utils_docker, utils_ec2
from ...utils.buffer_machines import (
    dump_pre_pulled_images_as_tags,
    list_pre_pulled_images_tag_keys,
    load_pre_pulled_images_from_tags,
)
from ...utils.cluster_scaling import (
    associate_ec2_instances_with_nodes,
    ec2_startup_script,
    find_selected_instance_type_for_task,
    get_hot_buffer_type,
    sort_drained_nodes,
)
from ...utils.rabbitmq import (
    post_autoscaling_status_message,
    post_tasks_log_message,
    post_tasks_progress_message,
)
from ...utils.warm_buffer_machines import (
    get_activated_warm_buffer_ec2_tags,
    get_deactivated_warm_buffer_ec2_tags,
    is_warm_buffer_machine,
)
from ..docker import get_docker_client
from ..ec2 import get_ec2_client
from ..instrumentation import get_instrumentation, has_instrumentation
from ..ssm import get_ssm_client
from ._provider_protocol import AutoscalingProvider


@dataclasses.dataclass(frozen=True, kw_only=True)
class InstanceToLaunch:
    """Represents a single EC2 instance to launch with its specific labels.

    Each instance gets ONLY the labels from its assigned tasks (exclusive labels).
    """

    instance_type: EC2InstanceType
    node_labels: dict[DockerLabelKey, str]

    def __hash__(self) -> int:
        return hash((self.instance_type, frozenset(self.node_labels.items())))


_logger = logging.getLogger(__name__)


async def _analyze_current_cluster(
    app: FastAPI,
    auto_scaling_mode: AutoscalingProvider,
    allowed_instance_types: list[EC2InstanceType],
) -> Cluster:
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec

    # get current docker nodes (these are associated (active or drained) or disconnected)
    docker_nodes: list[Node] = await auto_scaling_mode.get_monitored_nodes(app)

    # get the EC2 instances we have
    existing_ec2_instances: list[EC2InstanceData] = await get_ec2_client(
        app
    ).get_instances(
        key_names=[app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_KEY_NAME],
        tags=auto_scaling_mode.get_ec2_tags(app),
        state_names=["pending", "running"],
    )

    terminated_ec2_instances: list[EC2InstanceData] = await get_ec2_client(
        app
    ).get_instances(
        key_names=[app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_KEY_NAME],
        tags=auto_scaling_mode.get_ec2_tags(app),
        state_names=["terminated"],
    )

    warm_buffer_ec2_instances: list[EC2InstanceData] = await get_ec2_client(
        app
    ).get_instances(
        key_names=[app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_KEY_NAME],
        tags=get_deactivated_warm_buffer_ec2_tags(auto_scaling_mode.get_ec2_tags(app)),
        state_names=["stopped"],
    )

    for i in itertools.chain(existing_ec2_instances, warm_buffer_ec2_instances):
        auto_scaling_mode.add_instance_generic_resources(app, i)

    attached_ec2s, pending_ec2s = associate_ec2_instances_with_nodes(
        docker_nodes, existing_ec2_instances
    )

    # analyse pending ec2s, check if they are pending since too long
    now = arrow.utcnow().datetime
    broken_ec2s = [
        instance
        for instance in pending_ec2s
        if (now - instance.launch_time)
        > app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_START_TIME
    ]
    if broken_ec2s:
        _logger.error(
            "Detected broken EC2 instances that never joined the cluster after %s: %s\n"
            "TIP: if this happens very often the time to start an EC2 might have increased or "
            "something might be wrong with the used AMI and/or boot script in which case this"
            " would happen all the time. Please check",
            app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_START_TIME,
            f"{[_.id for _ in broken_ec2s]}",
        )
    # remove the broken ec2s from the pending ones
    pending_ec2s = [
        instance for instance in pending_ec2s if instance not in broken_ec2s
    ]

    # analyse attached ec2s
    active_nodes, pending_nodes, all_drained_nodes, retired_nodes = [], [], [], []
    for instance in attached_ec2s:
        if await auto_scaling_mode.is_instance_active(app, instance):
            node_used_resources = await auto_scaling_mode.compute_node_used_resources(
                app, instance
            )
            active_nodes.append(
                dataclasses.replace(
                    instance,
                    available_resources=instance.ec2_instance.resources
                    - node_used_resources,
                )
            )
        elif utils_docker.is_instance_drained(instance):
            all_drained_nodes.append(instance)
        elif await auto_scaling_mode.is_instance_retired(app, instance):
            # it should be drained, but it is not, so we force it to be drained such that it might be re-used if needed
            retired_nodes.append(instance)
        else:
            pending_nodes.append(instance)

    drained_nodes, hot_buffer_drained_nodes, terminating_nodes = sort_drained_nodes(
        app_settings, all_drained_nodes, allowed_instance_types
    )
    cluster = Cluster(
        active_nodes=active_nodes,
        pending_nodes=pending_nodes,
        drained_nodes=drained_nodes,
        hot_buffer_drained_nodes=hot_buffer_drained_nodes,
        pending_ec2s=[NonAssociatedInstance(ec2_instance=i) for i in pending_ec2s],
        broken_ec2s=[NonAssociatedInstance(ec2_instance=i) for i in broken_ec2s],
        warm_buffer_ec2s=[
            NonAssociatedInstance(ec2_instance=i) for i in warm_buffer_ec2_instances
        ],
        terminating_nodes=terminating_nodes,
        terminated_instances=[
            NonAssociatedInstance(ec2_instance=i) for i in terminated_ec2_instances
        ],
        disconnected_nodes=[
            n for n in docker_nodes if not utils_docker.is_node_ready(n)
        ],
        retired_nodes=retired_nodes,
    )
    _logger.info("current state: %s", f"{cluster!r}")
    return cluster


_DELAY_FOR_REMOVING_DISCONNECTED_NODES_S: Final[int] = 30


async def _cleanup_disconnected_nodes(app: FastAPI, cluster: Cluster) -> Cluster:
    utc_now = arrow.utcnow().datetime
    removable_nodes = [
        node
        for node in cluster.disconnected_nodes
        if node.updated_at
        and (
            (utc_now - arrow.get(node.updated_at).datetime).total_seconds()
            > _DELAY_FOR_REMOVING_DISCONNECTED_NODES_S
        )
    ]
    if removable_nodes:
        await utils_docker.remove_nodes(get_docker_client(app), nodes=removable_nodes)
    return dataclasses.replace(cluster, disconnected_nodes=[])


async def _terminate_broken_ec2s(app: FastAPI, cluster: Cluster) -> Cluster:
    broken_instances = [i.ec2_instance for i in cluster.broken_ec2s]
    if broken_instances:
        with log_context(
            _logger, logging.WARNING, msg="terminate broken EC2 instances"
        ):
            await get_ec2_client(app).terminate_instances(broken_instances)

    return dataclasses.replace(
        cluster,
        broken_ec2s=[],
        terminated_instances=cluster.terminated_instances + cluster.broken_ec2s,
    )


async def _make_pending_warm_buffer_ec2s_join_cluster(
    app: FastAPI,
    cluster: Cluster,
) -> Cluster:
    ec2_client = get_ec2_client(app)
    if buffer_ec2s_pending := [
        i.ec2_instance
        for i in cluster.pending_ec2s
        if is_warm_buffer_machine(i.ec2_instance.tags)
        and (DOCKER_JOIN_COMMAND_EC2_TAG_KEY not in i.ec2_instance.tags)
    ]:
        # started buffer instance shall be asked to join the cluster once they are running
        app_settings = get_application_settings(app)
        ssm_client = get_ssm_client(app)

        buffer_ec2_connection_state = await limited_gather(
            *[
                ssm_client.is_instance_connected_to_ssm_server(i.id)
                for i in buffer_ec2s_pending
            ],
            reraise=False,
            log=_logger,
            limit=20,
        )
        buffer_ec2_connected_to_ssm_server = [
            i
            for i, c in zip(
                buffer_ec2s_pending, buffer_ec2_connection_state, strict=True
            )
            if c is True
        ]
        buffer_ec2_ready_for_command = buffer_ec2_connected_to_ssm_server
        if app_settings.AUTOSCALING_WAIT_FOR_CLOUD_INIT_BEFORE_WARM_BUFFER_ACTIVATION:
            buffer_ec2_initialized = await limited_gather(
                *[
                    ssm_client.wait_for_has_instance_completed_cloud_init(i.id)
                    for i in buffer_ec2_connected_to_ssm_server
                ],
                reraise=False,
                log=_logger,
                limit=20,
            )
            buffer_ec2_ready_for_command = [
                i
                for i, r in zip(
                    buffer_ec2_connected_to_ssm_server,
                    buffer_ec2_initialized,
                    strict=True,
                )
                if r is True
            ]
        if buffer_ec2_ready_for_command:
            ssm_command = await ssm_client.send_command(
                [i.id for i in buffer_ec2_ready_for_command],
                command=await utils_docker.get_docker_swarm_join_bash_command(
                    join_as_drained=app_settings.AUTOSCALING_DOCKER_JOIN_DRAINED
                ),
                command_name=DOCKER_JOIN_COMMAND_NAME,
            )
            await ec2_client.set_instances_tags(
                buffer_ec2_ready_for_command,
                tags={
                    DOCKER_JOIN_COMMAND_EC2_TAG_KEY: ssm_command.command_id,
                },
            )
    return cluster


async def _try_attach_pending_ec2s(
    app: FastAPI,
    cluster: Cluster,
    auto_scaling_mode: AutoscalingProvider,
    allowed_instance_types: list[EC2InstanceType],
) -> Cluster:
    """label the drained instances that connected to the swarm which are missing the monitoring labels"""
    new_found_instances: list[AssociatedInstance] = []
    still_pending_ec2s: list[NonAssociatedInstance] = []
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    ec2_instances_to_remove_custom_label_tags: list[EC2InstanceData] = []

    for instance_data in cluster.pending_ec2s:
        try:
            node_host_name = utils_ec2.node_host_name_from_ec2_private_dns(
                instance_data.ec2_instance
            )
            if new_node := await utils_docker.find_node_with_name(
                get_docker_client(app), node_host_name
            ):
                # Get base tags from provider
                base_tags = auto_scaling_mode.get_new_node_docker_tags(
                    app, instance_data.ec2_instance
                )

                # Load custom placement labels from EC2 tags if any
                try:
                    custom_labels_dict = (
                        utils_ec2.load_custom_placement_labels_from_tags(
                            instance_data.ec2_instance.tags
                        )
                    )
                except Ec2TagDeserializationError as err:
                    _logger.exception(
                        **create_troubleshooting_log_kwargs(
                            f"could not deserialize custom placement labels from EC2 tags for {instance_data.ec2_instance.id}",
                            error=err,
                            tip="Check the invalid syntax of the custom placement labels EC2 tag",
                        )
                    )
                    custom_labels_dict = {}

                # Merge base tags with custom labels
                merged_tags = base_tags | custom_labels_dict

                # Attach node with merged tags
                new_node = await utils_docker.attach_node(
                    app_settings,
                    get_docker_client(app),
                    new_node,
                    tags=merged_tags,
                )

                # Mark instance for EC2 tag cleanup if custom labels were applied
                if custom_labels_dict:
                    ec2_instances_to_remove_custom_label_tags.append(
                        instance_data.ec2_instance
                    )

                new_found_instances.append(
                    AssociatedInstance(
                        node=new_node, ec2_instance=instance_data.ec2_instance
                    )
                )
                _logger.info(
                    "Attached new EC2 instance %s with custom placement labels: %s",
                    instance_data.ec2_instance.id,
                    custom_labels_dict,
                )
            else:
                still_pending_ec2s.append(instance_data)
        except Ec2InvalidDnsNameError:
            _logger.exception("Unexpected EC2 private dns")

    # Remove custom label EC2 tags after successful attachment
    if ec2_instances_to_remove_custom_label_tags and (
        tag_keys := utils_ec2.list_custom_placement_label_tag_keys(
            ec2_instances_to_remove_custom_label_tags[0].tags
        )
    ):
        await get_ec2_client(app).remove_instances_tags(
            ec2_instances_to_remove_custom_label_tags,
            tag_keys=tag_keys,
        )

    # NOTE: first provision the reserve drained nodes if possible
    all_drained_nodes = (
        cluster.drained_nodes + cluster.hot_buffer_drained_nodes + new_found_instances
    )
    drained_nodes, hot_buffer_drained_nodes, _ = sort_drained_nodes(
        app_settings, all_drained_nodes, allowed_instance_types
    )
    return dataclasses.replace(
        cluster,
        drained_nodes=drained_nodes,
        hot_buffer_drained_nodes=hot_buffer_drained_nodes,
        pending_ec2s=still_pending_ec2s,
    )


async def _sorted_allowed_instance_types(
    app: FastAPI, auto_scaling_mode: AutoscalingProvider
) -> list[EC2InstanceType]:
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    ec2_client = get_ec2_client(app)

    allowed_instance_type_names = list(
        app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES
    )

    assert (  # nosec
        allowed_instance_type_names
    ), "EC2_INSTANCES_ALLOWED_TYPES cannot be empty!"

    allowed_instance_types: list[EC2InstanceType] = (
        await ec2_client.get_ec2_instance_capabilities(
            cast(set[InstanceTypeType], set(allowed_instance_type_names))
        )
    )

    def _as_selection(instance_type: EC2InstanceType) -> int:
        # NOTE: will raise ValueError if allowed_instance_types not in allowed_instance_type_names
        return allowed_instance_type_names.index(f"{instance_type.name}")

    return [
        auto_scaling_mode.adjust_instance_type_resources(app, instance_type)
        for instance_type in sorted(allowed_instance_types, key=_as_selection)
    ]


async def _activate_and_notify(
    app: FastAPI,
    drained_node: AssociatedInstance,
) -> AssociatedInstance:
    app_settings = get_application_settings(app)
    docker_client = get_docker_client(app)
    updated_node, *_ = await asyncio.gather(
        utils_docker.set_node_osparc_ready(
            app_settings, docker_client, drained_node.node, ready=True
        ),
        post_tasks_log_message(
            app,
            tasks=drained_node.assigned_tasks,
            message="cluster adjusted, service should start shortly...",
            level=logging.INFO,
        ),
        post_tasks_progress_message(
            app,
            tasks=drained_node.assigned_tasks,
            progress=1.0,
            progress_type=ProgressType.CLUSTER_UP_SCALING,
        ),
    )
    return dataclasses.replace(drained_node, node=updated_node)


async def _cancel_previous_pulling_command_if_any(
    app: FastAPI,
    instance: EC2InstanceData,
) -> None:
    if not (
        (MACHINE_PULLING_EC2_TAG_KEY in instance.tags)
        and (MACHINE_PULLING_COMMAND_ID_EC2_TAG_KEY in instance.tags)
    ):
        # nothing to do
        return

    ssm_client = get_ssm_client(app)
    ec2_client = get_ec2_client(app)
    command_id = instance.tags[MACHINE_PULLING_COMMAND_ID_EC2_TAG_KEY]
    command = await ssm_client.get_command(instance.id, command_id=command_id)
    if command.status in ("Pending", "InProgress"):
        with log_context(
            _logger,
            logging.INFO,
            msg=f"cancelling previous pulling {command_id} on {instance.id}",
        ):
            await ssm_client.cancel_command(instance.id, command_id=command_id)
        await ec2_client.remove_instances_tags(
            [instance],
            tag_keys=[
                MACHINE_PULLING_COMMAND_ID_EC2_TAG_KEY,
                MACHINE_PULLING_EC2_TAG_KEY,
                *list_pre_pulled_images_tag_keys(instance.tags),
            ],
        )


async def _activate_drained_nodes(
    app: FastAPI,
    cluster: Cluster,
) -> Cluster:
    nodes_to_activate = [
        node
        for node in itertools.chain(
            cluster.drained_nodes, cluster.hot_buffer_drained_nodes
        )
        if node.assigned_tasks
    ]

    if not nodes_to_activate:
        return cluster

    with log_context(
        _logger,
        logging.INFO,
        f"activate {len(nodes_to_activate)} drained nodes {[n.ec2_instance.id for n in nodes_to_activate]}",
    ):
        await asyncio.gather(
            *(
                _cancel_previous_pulling_command_if_any(app, n.ec2_instance)
                for n in nodes_to_activate
            )
        )
        activated_nodes = await asyncio.gather(
            *(_activate_and_notify(app, node) for node in nodes_to_activate)
        )
    new_active_node_ids = {node.ec2_instance.id for node in activated_nodes}
    remaining_drained_nodes = [
        node
        for node in cluster.drained_nodes
        if node.ec2_instance.id not in new_active_node_ids
    ]
    remaining_reserved_drained_nodes = [
        node
        for node in cluster.hot_buffer_drained_nodes
        if node.ec2_instance.id not in new_active_node_ids
    ]
    return dataclasses.replace(
        cluster,
        active_nodes=cluster.active_nodes + activated_nodes,
        drained_nodes=remaining_drained_nodes,
        hot_buffer_drained_nodes=remaining_reserved_drained_nodes,
    )


def _de_assign_tasks_from_warm_buffer_ec2s(
    cluster: Cluster, instances_to_start: list[EC2InstanceData]
) -> tuple[Cluster, list]:
    # de-assign tasks from the warm buffer instances that could not be started
    deassigned_tasks = list(
        itertools.chain.from_iterable(
            i.assigned_tasks
            for i in cluster.warm_buffer_ec2s
            if i.ec2_instance in instances_to_start
        )
    )
    # upgrade the cluster
    return (
        dataclasses.replace(
            cluster,
            warm_buffer_ec2s=[
                (
                    dataclasses.replace(i, assigned_tasks=[])
                    if i.ec2_instance in instances_to_start
                    else i
                )
                for i in cluster.warm_buffer_ec2s
            ],
        ),
        deassigned_tasks,
    )


async def _try_start_warm_buffer_instances(
    app: FastAPI, cluster: Cluster, auto_scaling_mode: AutoscalingProvider
) -> tuple[Cluster, list]:
    """
    starts warm buffer if there are assigned tasks, or if a hot buffer of the same type is needed

    Returns:
        A tuple containing:
            - The updated cluster instance after attempting to start warm buffer instances.
            - In case warm buffer could not be started, a list of de-assigned tasks (tasks whose resource requirements cannot be fulfilled by warm buffers anymore).

    """

    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec

    instances_to_start = [
        i.ec2_instance for i in cluster.warm_buffer_ec2s if i.assigned_tasks
    ]

    if (
        len(cluster.hot_buffer_drained_nodes)
        < app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER
    ):
        # check if we can migrate warm buffers to hot buffers
        hot_buffer_instance_type = cast(
            InstanceTypeType,
            next(
                iter(app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES)
            ),
        )
        free_startable_warm_buffers_to_replace_hot_buffers = [
            warm_buffer.ec2_instance
            for warm_buffer in cluster.warm_buffer_ec2s
            if (warm_buffer.ec2_instance.type == hot_buffer_instance_type)
            and not warm_buffer.assigned_tasks
        ]
        # check there are no empty pending ec2s/nodes that are not assigned to any task
        unnassigned_pending_ec2s = [
            i.ec2_instance for i in cluster.pending_ec2s if not i.assigned_tasks
        ]
        unnassigned_pending_nodes = [
            i.ec2_instance for i in cluster.pending_nodes if not i.assigned_tasks
        ]

        instances_to_start += free_startable_warm_buffers_to_replace_hot_buffers[
            : app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER
            - len(cluster.hot_buffer_drained_nodes)
            - len(unnassigned_pending_ec2s)
            - len(unnassigned_pending_nodes)
        ]

    if not instances_to_start:
        return cluster, []

    with log_context(
        _logger,
        logging.INFO,
        f"start {len(instances_to_start)} warm buffer machines '{[i.id for i in instances_to_start]}'",
    ):
        try:
            started_instances = await get_ec2_client(app).start_instances(
                instances_to_start
            )
        except EC2InsufficientCapacityError:
            # NOTE: this warning is only raised if none of the instances could be started due to InsufficientCapacity
            _logger.warning(
                "Could not start warm buffer instances: %s due to Insufficient Capacity in the current AWS Availability Zone! "
                "The warm buffer assigned tasks will be moved to new instances if possible.",
                [i.id for i in instances_to_start],
            )
            return _de_assign_tasks_from_warm_buffer_ec2s(cluster, instances_to_start)

        except EC2AccessError:
            _logger.exception(
                "Could not start warm buffer instances %s! TIP: This needs to be analysed!"
                "The warm buffer assigned tasks will be moved to new instances if possible.",
                [i.id for i in instances_to_start],
            )
            return _de_assign_tasks_from_warm_buffer_ec2s(cluster, instances_to_start)

        # NOTE: first start the instance and then set the tags in case the instance cannot start (e.g. InsufficientInstanceCapacity)
        await get_ec2_client(app).set_instances_tags(
            started_instances,
            tags=get_activated_warm_buffer_ec2_tags(
                auto_scaling_mode.get_ec2_tags(app)
            ),
        )
    started_instance_ids = [i.id for i in started_instances]

    return (
        dataclasses.replace(
            cluster,
            warm_buffer_ec2s=[
                i
                for i in cluster.warm_buffer_ec2s
                if i.ec2_instance.id not in started_instance_ids
            ],
            pending_ec2s=cluster.pending_ec2s
            + [NonAssociatedInstance(ec2_instance=i) for i in started_instances],
        ),
        [],
    )


def _try_assign_task_to_ec2_instance(
    task,
    *,
    instances: list[AssociatedInstance] | list[NonAssociatedInstance],
    task_required_ec2_instance: InstanceTypeType | None,
    task_required_resources: Resources,
    task_required_docker_node_labels: dict[DockerLabelKey, str],
) -> bool:
    for instance in instances:
        # Check EC2 instance type
        if task_required_ec2_instance and (
            task_required_ec2_instance != instance.ec2_instance.type
        ):
            continue

        # Check custom placement labels
        if (
            isinstance(instance, AssociatedInstance)
            and task_required_docker_node_labels
        ):
            assert instance.node.spec  # nosec
            node_labels = instance.node.spec.labels if instance.node.spec.labels else {}
            # Verify that all required labels match
            if any(
                node_labels.get(label_key) != label_value
                for label_key, label_value in task_required_docker_node_labels.items()
            ):
                continue

        # Check resources
        if instance.has_resources_for_task(task_required_resources):
            instance.assign_task(task, task_required_resources)
            _logger.debug(
                "%s",
                f"assigned task with {task_required_resources=}, {task_required_ec2_instance=}, "
                f"{task_required_docker_node_labels=} to {instance.ec2_instance.id=}:{instance.ec2_instance.type=}, "
                f"{instance.available_resources=}, {instance.ec2_instance.resources=}",
            )
            return True
    return False


def _try_assign_task_to_ec2_instance_type(
    task,
    *,
    instances: list[AssignedTasksToInstanceType],
    task_required_ec2_instance: InstanceTypeType | None,
    task_required_resources: Resources,
    task_required_labels: dict[DockerLabelKey, str],
) -> bool:
    """Try to assign task to an existing instance being created.

    Returns True if task was assigned, False otherwise.
    Task can only be assigned if:
    - Instance type matches (if specified)
    - Resources are available
    - Labels are compatible (no conflicting label values)
    """
    for instance in instances:
        if task_required_ec2_instance and (
            task_required_ec2_instance != instance.instance_type.name
        ):
            continue
        if not instance.has_resources_for_task(task_required_resources):
            continue

        # Check label compatibility
        if not instance.has_compatible_labels(task_required_labels):
            continue

        # Compatible! Assign task and merge labels
        instance.assign_task(task, task_required_resources)
        _logger.debug(
            "%s",
            f"assigned task with {task_required_resources=}, {task_required_ec2_instance=}, labels={task_required_labels} to "
            f"{instance.instance_type=}, "
            f"{instance.available_resources=}, instance_labels={instance.osparc_custom_node_labels}",
        )
        return True
    return False


async def _assign_tasks_to_current_cluster(
    app: FastAPI,
    tasks: list,
    cluster: Cluster,
    auto_scaling_mode: AutoscalingProvider,
) -> tuple[list, Cluster]:
    """
        Evaluates whether a task can be executed on any instance within the cluster. If the task's resource requirements are met, the task is *denoted* as assigned to the cluster.
        Note: This is an estimation only since actual scheduling is handled by Dask/Docker (depending on the mode).

    Returns:
        A tuple containing:
            - A list of unassigned tasks (tasks whose resource requirements cannot be fulfilled by the available machines in the cluster).
            - The same cluster instance passed as input.
    """
    unassigned_tasks = []
    assignment_predicates = [
        functools.partial(_try_assign_task_to_ec2_instance, instances=instances)
        for instances in (
            cluster.active_nodes,
            cluster.drained_nodes + cluster.hot_buffer_drained_nodes,
            cluster.pending_nodes,
            cluster.pending_ec2s,
            cluster.warm_buffer_ec2s,
        )
    ]

    for task in tasks:
        task_required_resources = auto_scaling_mode.get_task_required_resources(task)
        task_required_ec2_instance = await auto_scaling_mode.get_task_defined_instance(
            app, task
        )
        task_required_labels = (
            await auto_scaling_mode.get_task_instance_required_docker_tags(app, task)
        )

        if any(
            is_assigned(
                task,
                task_required_ec2_instance=task_required_ec2_instance,
                task_required_resources=task_required_resources,
                task_required_docker_node_labels=task_required_labels,
            )
            for is_assigned in assignment_predicates
        ):
            _logger.debug(
                "task %s is assigned to one instance available in cluster", task
            )
        else:
            unassigned_tasks.append(task)

    if unassigned_tasks:
        _logger.info(
            "the current cluster should cope with %s tasks, %s are unnassigned/queued "
            "tasks and need to wait or get new EC2s",
            len(tasks) - len(unassigned_tasks),
            len(unassigned_tasks),
        )
    return unassigned_tasks, cluster


async def _find_needed_instances(
    app: FastAPI,
    unassigned_tasks: list,
    available_ec2_types: list[EC2InstanceType],
    cluster: Cluster,
    auto_scaling_mode: AutoscalingProvider,
) -> dict[InstanceToLaunch, int]:
    # 1. check first the pending task needs
    # Track which tasks get assigned to which new instances
    needed_new_instance_types_for_tasks: list[AssignedTasksToInstanceType] = []

    with log_context(_logger, logging.DEBUG, msg="finding needed instances"):
        for task in unassigned_tasks:
            task_required_resources = auto_scaling_mode.get_task_required_resources(
                task
            )
            task_required_ec2 = await auto_scaling_mode.get_task_defined_instance(
                app, task
            )
            task_required_labels = (
                await auto_scaling_mode.get_task_instance_required_docker_tags(
                    app, task
                )
            )

            # first check if we can assign the task to one of the newly tobe created instances
            if _try_assign_task_to_ec2_instance_type(
                task,
                instances=needed_new_instance_types_for_tasks,
                task_required_ec2_instance=task_required_ec2,
                task_required_resources=task_required_resources,
                task_required_labels=task_required_labels,
            ):
                continue

            # so we need to find what we can create now
            try:
                # check if exact instance type is needed first
                if task_required_ec2:
                    defined_ec2 = find_selected_instance_type_for_task(
                        task_required_ec2,
                        available_ec2_types,
                        task,
                        task_required_resources,
                    )
                    needed_new_instance_types_for_tasks.append(
                        AssignedTasksToInstanceType(
                            instance_type=defined_ec2,
                            assigned_tasks=[task],
                            available_resources=defined_ec2.resources
                            - task_required_resources,
                            osparc_custom_node_labels=task_required_labels,
                        )
                    )
                else:
                    # we go for best fitting type
                    best_ec2_instance = utils_ec2.find_best_fitting_ec2_instance(
                        available_ec2_types,
                        task_required_resources,
                        score_type=utils_ec2.closest_instance_policy,
                    )
                    needed_new_instance_types_for_tasks.append(
                        AssignedTasksToInstanceType(
                            instance_type=best_ec2_instance,
                            assigned_tasks=[task],
                            available_resources=best_ec2_instance.resources
                            - task_required_resources,
                            osparc_custom_node_labels=task_required_labels,
                        )
                    )
            except TaskBestFittingInstanceNotFoundError:
                _logger.exception("Task %s needs more resources: ", f"{task}")
            except (
                TaskRequirementsAboveRequiredEC2InstanceTypeError,
                TaskRequiresUnauthorizedEC2InstanceTypeError,
            ):
                _logger.exception("Unexpected error:")

    _logger.info(
        "found %d required instances: %s",
        len(needed_new_instance_types_for_tasks),
        ", ".join(
            f"{i.instance_type.name}:{i.instance_type.resources} for {len(i.assigned_tasks)} task{'s' if len(i.assigned_tasks) > 1 else ''}"
            for i in needed_new_instance_types_for_tasks
        ),
    )

    # Build counts of identical instance batches using Counter
    instances_with_counts = collections.Counter(
        InstanceToLaunch(
            instance_type=assigned_instance.instance_type,
            node_labels=assigned_instance.osparc_custom_node_labels.copy(),
        )
        for assigned_instance in needed_new_instance_types_for_tasks
    )

    # 2. check the hot buffer needs
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    if (
        num_missing_nodes := (
            app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER
            - len(cluster.hot_buffer_drained_nodes)
        )
    ) > 0:
        # check if some are already pending
        remaining_pending_instances = [
            i.ec2_instance for i in cluster.pending_ec2s if not i.assigned_tasks
        ] + [i.ec2_instance for i in cluster.pending_nodes if not i.assigned_tasks]
        if len(remaining_pending_instances) < (
            app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER
            - len(cluster.hot_buffer_drained_nodes)
        ):
            default_instance_type = get_hot_buffer_type(available_ec2_types)
            instances_with_counts[
                InstanceToLaunch(instance_type=default_instance_type, node_labels={})
            ] += num_missing_nodes

    _logger.info(
        "prepared %d batches of instances to launch: %s",
        len(instances_with_counts),
        ", ".join(
            f"{count}x {instance.instance_type.name} with labels {instance.node_labels}"
            for instance, count in instances_with_counts.items()
        ),
    )

    return dict(instances_with_counts)


async def _cap_needed_instances(
    app: FastAPI, needed_instances: dict[InstanceToLaunch, int], ec2_tags: EC2Tags
) -> dict[InstanceToLaunch, int]:
    """Caps the needed instances dict[InstanceToLaunch, int] to the maximal allowed number of instances.

    Uses proportional distribution when capping is needed - if we need 10 instances of a type but can only
    create 5, each batch with that type gets proportionally reduced.

    NOTE: the maximum allowed number of instances contains the current number of running/pending machines

    Raises:
        Ec2TooManyInstancesError: raised when the maximum of machines is already running/pending
    """
    ec2_client = get_ec2_client(app)
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    current_instances = await ec2_client.get_instances(
        key_names=[app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_KEY_NAME],
        tags=ec2_tags,
    )
    current_number_of_instances = len(current_instances)
    # 1. Check current capacity, raise if already at max
    if (
        current_number_of_instances
        >= app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES
    ):
        raise EC2TooManyInstancesError(
            num_instances=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES
        )

    # 2. Check if needed instances fit, otherwise cap proportionally
    total_number_of_needed_instances = sum(needed_instances.values())
    if (
        current_number_of_instances + total_number_of_needed_instances
        <= app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES
    ):
        # ok that fits no need to do anything here
        return needed_instances

    # 3. we need to cap
    max_number_of_creatable_instances = (
        app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES
        - current_number_of_instances
    )

    # Start by creating 1 instance of each needed type
    needed_by_type = collections.Counter(
        {
            instance_batch.instance_type: count
            for instance_batch, count in needed_instances.items()
        }
    )
    if max_number_of_creatable_instances < len(needed_by_type):
        # Not enough capacity for creating 1 instance of each type, create as many as possible
        capped_instances: dict[InstanceToLaunch, int] = {}
        for idx, instance_batch in enumerate(needed_instances.keys()):
            if (idx + 1) > max_number_of_creatable_instances:
                break
            capped_instances[instance_batch] = 1
        return capped_instances

    capped_by_type: collections.Counter[EC2InstanceType] = collections.Counter(
        {
            instance_type: 1
            for idx, instance_type in enumerate(needed_by_type)
            if (idx + 1) <= max_number_of_creatable_instances
        }
    )

    # Increase counts round-robin until capacity reached
    while capped_by_type.total() < max_number_of_creatable_instances:
        for instance_type in needed_by_type:
            if capped_by_type.total() == max_number_of_creatable_instances:
                break
            if needed_by_type[instance_type] > capped_by_type[instance_type]:
                capped_by_type[instance_type] += 1

    # Distribute capped counts proportionally to InstanceToLaunch batches
    result: dict[InstanceToLaunch, int] = {}
    for instance_batch, original_count in needed_instances.items():
        instance_type = instance_batch.instance_type
        capped_total = capped_by_type[instance_type]
        original_total = needed_by_type[instance_type]

        proportional_count = int(original_count * capped_total / original_total)
        if proportional_count > 0:
            result[instance_batch] = proportional_count

    # Handle rounding errors - distribute remaining instances
    remaining = max_number_of_creatable_instances - sum(result.values())
    for instance_batch in needed_instances:
        if remaining == 0:
            break
        if instance_batch in result:
            result[instance_batch] += 1
            remaining -= 1

    return result


async def _launch_instances(
    app: FastAPI,
    instances_to_launch: dict[InstanceToLaunch, int],
    tasks: list,
    auto_scaling_mode: AutoscalingProvider,
) -> list[EC2InstanceData]:
    """Launch EC2 instances, each with its specific node labels.

    Each instance gets only the labels required by its assigned tasks (exclusive labels).
    """
    ec2_client = get_ec2_client(app)
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    base_tags = auto_scaling_mode.get_ec2_tags(app)

    # Cap instances based on cluster capacity
    try:
        capped_instances = await _cap_needed_instances(
            app, instances_to_launch, base_tags
        )
    except EC2TooManyInstancesError:
        await post_tasks_log_message(
            app,
            tasks=tasks,
            message="The maximum number of machines in the cluster was reached. Please wait for your running jobs "
            "to complete and try again later or contact osparc support if this issue does not resolve.",
            level=logging.ERROR,
        )
        return []

    # Launch batched instances with their specific labels
    results = await asyncio.gather(
        *[
            ec2_client.launch_instances(
                EC2InstanceConfig(
                    type=instance_batch.instance_type,
                    tags=(
                        base_tags
                        | (
                            utils_ec2.dump_custom_placement_labels_as_tags(
                                instance_batch.node_labels
                            )
                            if instance_batch.node_labels
                            else {}
                        )
                    ),
                    startup_script=await ec2_startup_script(
                        app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES[
                            instance_batch.instance_type.name
                        ],
                        app_settings,
                    ),
                    ami_id=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES[
                        instance_batch.instance_type.name
                    ].ami_id,
                    key_name=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_KEY_NAME,
                    security_group_ids=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_SECURITY_GROUP_IDS,
                    subnet_ids=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_SUBNET_IDS,
                    iam_instance_profile=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ATTACHED_IAM_PROFILE,
                ),
                min_number_of_instances=1,  # NOTE: we want at least 1 if possible
                number_of_instances=capped_count,  # Launch batch of instances with same type and labels
                max_total_number_of_instances=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES,
            )
            for instance_batch, capped_count in capped_instances.items()
        ],
        return_exceptions=True,
    )
    # parse results
    last_issue = ""
    new_pending_instances: list[EC2InstanceData] = []
    for r in results:
        if isinstance(r, EC2TooManyInstancesError):
            await post_tasks_log_message(
                app,
                tasks=tasks,
                message="Exceptionally high load on computational cluster, please try again later.",
                level=logging.ERROR,
            )
        elif isinstance(r, BaseException):
            _logger.error("Unexpected error happened when starting EC2 instance: %s", r)
            last_issue = f"{r}"
        elif isinstance(r, list):
            new_pending_instances.extend(r)
        else:
            new_pending_instances.append(r)

    log_message = (
        f"{sum(capped_instances.values())} new machines launched"
        f", it might take up to {timedelta_as_minute_second(app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_START_TIME)} minutes to start, Please wait..."
    )
    await post_tasks_log_message(
        app, tasks=tasks, message=log_message, level=logging.INFO
    )
    if last_issue:
        await post_tasks_log_message(
            app,
            tasks=tasks,
            message="Unexpected issues detected, probably due to high load, please contact support",
            level=logging.ERROR,
        )

    return new_pending_instances


async def _find_drainable_nodes(
    app: FastAPI, cluster: Cluster
) -> list[AssociatedInstance]:
    app_settings: ApplicationSettings = app.state.settings
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec

    if not cluster.active_nodes:
        # there is nothing to drain here
        return []

    # get the corresponding ec2 instance data
    drainable_nodes: list[AssociatedInstance] = []

    for instance in cluster.active_nodes:
        if instance.has_assigned_tasks():
            await utils_docker.set_node_found_empty(
                get_docker_client(app), instance.node, empty=False
            )
            continue
        node_last_empty = await utils_docker.get_node_empty_since(instance.node)
        if not node_last_empty:
            await utils_docker.set_node_found_empty(
                get_docker_client(app), instance.node, empty=True
            )
            continue
        elapsed_time_since_empty = arrow.utcnow().datetime - node_last_empty
        _logger.debug("%s", f"{node_last_empty=}, {elapsed_time_since_empty=}")
        if (
            elapsed_time_since_empty
            > app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_DRAINING
        ):
            drainable_nodes.append(instance)
        else:
            _logger.info(
                "%s has still %ss before being drainable",
                f"{instance.ec2_instance.id=}",
                f"{(app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_DRAINING - elapsed_time_since_empty).total_seconds():.0f}",
            )

    if drainable_nodes:
        _logger.info(
            "the following nodes were found to be drainable: '%s'",
            f"{[instance.node.description.hostname for instance in drainable_nodes if instance.node.description]}",
        )
    return drainable_nodes


async def _deactivate_empty_nodes(app: FastAPI, cluster: Cluster) -> Cluster:
    app_settings = get_application_settings(app)
    docker_client = get_docker_client(app)
    active_empty_instances = await _find_drainable_nodes(app, cluster)

    if not active_empty_instances:
        return cluster

    with log_context(
        _logger, logging.INFO, f"drain {len(active_empty_instances)} empty nodes"
    ):
        updated_nodes = await asyncio.gather(
            *(
                utils_docker.set_node_osparc_ready(
                    app_settings,
                    docker_client,
                    node.node,
                    ready=False,
                )
                for node in active_empty_instances
            )
        )
        if updated_nodes:
            _logger.info(
                "following nodes were set to drain: '%s'",
                f"{[node.description.hostname for node in updated_nodes if node.description]}",
            )
    newly_drained_instances = [
        AssociatedInstance(node=node, ec2_instance=instance.ec2_instance)
        for instance, node in zip(active_empty_instances, updated_nodes, strict=True)
    ]
    return dataclasses.replace(
        cluster,
        active_nodes=[
            n for n in cluster.active_nodes if n not in active_empty_instances
        ],
        drained_nodes=cluster.drained_nodes + newly_drained_instances,
    )


def _find_terminateable_instances(
    app: FastAPI, cluster: Cluster
) -> list[AssociatedInstance]:
    app_settings: ApplicationSettings = app.state.settings
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec

    if not cluster.drained_nodes:
        # there is nothing to terminate here
        return []

    # get the corresponding ec2 instance data
    terminateable_nodes: list[AssociatedInstance] = []

    for instance in cluster.drained_nodes:
        node_last_updated = utils_docker.get_node_last_readiness_update(instance.node)
        elapsed_time_since_drained = (
            datetime.datetime.now(datetime.UTC) - node_last_updated
        )
        _logger.debug("%s", f"{node_last_updated=}, {elapsed_time_since_drained=}")
        if (
            elapsed_time_since_drained
            > app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
        ):
            # let's terminate that one
            terminateable_nodes.append(instance)
        else:
            _logger.info(
                "%s has still %ss before being terminateable",
                f"{instance.ec2_instance.id=}",
                f"{(app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION - elapsed_time_since_drained).total_seconds():.0f}",
            )

    if terminateable_nodes:
        _logger.info(
            "the following nodes were found to be terminateable: '%s'",
            f"{[instance.node.description.hostname for instance in terminateable_nodes if instance.node.description]}",
        )
    return terminateable_nodes


async def _try_scale_down_cluster(app: FastAPI, cluster: Cluster) -> Cluster:
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    # instances found to be terminateable will now start the termination process.
    new_terminating_instances = []
    for instance in _find_terminateable_instances(app, cluster):
        assert instance.node.description is not None  # nosec
        with (
            log_context(
                _logger,
                logging.INFO,
                msg=f"termination process for {instance.node.description.hostname}:{instance.ec2_instance.id}",
            ),
            log_catch(_logger, reraise=False),
        ):
            await utils_docker.set_node_begin_termination_process(
                get_docker_client(app), instance.node
            )
            new_terminating_instances.append(instance)
    new_terminating_instance_ids = [
        i.ec2_instance.id for i in new_terminating_instances
    ]

    # instances that are in the termination process and already waited long enough are terminated.
    now = arrow.utcnow().datetime
    instances_to_terminate = [
        i
        for i in cluster.terminating_nodes
        if (now - (utils_docker.get_node_termination_started_since(i.node) or now))
        >= app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_FINAL_TERMINATION
    ]
    terminated_instance_ids = []
    if instances_to_terminate:
        with log_context(
            _logger,
            logging.INFO,
            msg=f"definitely terminate '{[i.node.description.hostname for i in instances_to_terminate if i.node.description]}'",
        ):
            await get_ec2_client(app).terminate_instances(
                [i.ec2_instance for i in instances_to_terminate]
            )

        # since these nodes are being terminated, remove them from the swarm
        await utils_docker.remove_nodes(
            get_docker_client(app),
            nodes=[i.node for i in instances_to_terminate],
            force=True,
        )
        terminated_instance_ids = [i.ec2_instance.id for i in instances_to_terminate]

    still_drained_nodes = [
        i
        for i in cluster.drained_nodes
        if i.ec2_instance.id
        not in (new_terminating_instance_ids + terminated_instance_ids)
    ]
    still_terminating_nodes = [
        i
        for i in cluster.terminating_nodes
        if i.ec2_instance.id not in terminated_instance_ids
    ]
    return dataclasses.replace(
        cluster,
        drained_nodes=still_drained_nodes,
        terminating_nodes=still_terminating_nodes + new_terminating_instances,
        terminated_instances=cluster.terminated_instances
        + [
            NonAssociatedInstance(ec2_instance=i.ec2_instance)
            for i in instances_to_terminate
        ],
    )


async def _notify_based_on_machine_type(
    app: FastAPI,
    instances: list[AssociatedInstance] | list[NonAssociatedInstance],
    *,
    message: str,
) -> None:
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    instance_max_time_to_start = (
        app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_START_TIME
    )
    launch_time_to_tasks: dict[datetime.datetime, list] = collections.defaultdict(list)
    now = datetime.datetime.now(datetime.UTC)
    for instance in instances:
        launch_time_to_tasks[
            instance.ec2_instance.launch_time
        ] += instance.assigned_tasks

    for launch_time, tasks in launch_time_to_tasks.items():
        time_since_launch = now - launch_time
        estimated_time_to_completion = launch_time + instance_max_time_to_start - now
        msg = (
            f"{message} (time waiting: {timedelta_as_minute_second(time_since_launch)},"
            f" est. remaining time: {timedelta_as_minute_second(estimated_time_to_completion)})...please wait..."
        )
        if tasks:
            await post_tasks_log_message(
                app, tasks=tasks, message=msg, level=logging.INFO
            )
            await post_tasks_progress_message(
                app,
                tasks=tasks,
                progress=time_since_launch.total_seconds()
                / instance_max_time_to_start.total_seconds(),
                progress_type=ProgressType.CLUSTER_UP_SCALING,
            )


async def _notify_machine_creation_progress(app: FastAPI, cluster: Cluster) -> None:
    await _notify_based_on_machine_type(
        app,
        cluster.pending_ec2s,
        message="waiting for machine to join cluster",
    )


async def _drain_retired_nodes(
    app: FastAPI,
    cluster: Cluster,
) -> Cluster:
    if not cluster.retired_nodes:
        return cluster

    app_settings = get_application_settings(app)
    docker_client = get_docker_client(app)
    # drain this empty nodes
    updated_nodes = await asyncio.gather(
        *(
            utils_docker.set_node_osparc_ready(
                app_settings,
                docker_client,
                node.node,
                ready=False,
            )
            for node in cluster.retired_nodes
        )
    )
    if updated_nodes:
        _logger.info(
            "following nodes were set to drain: '%s'",
            f"{[node.description.hostname for node in updated_nodes if node.description]}",
        )
    newly_drained_instances = [
        AssociatedInstance(node=node, ec2_instance=instance.ec2_instance)
        for instance, node in zip(cluster.retired_nodes, updated_nodes, strict=True)
    ]
    return dataclasses.replace(
        cluster,
        retired_nodes=[],
        drained_nodes=cluster.drained_nodes + newly_drained_instances,
    )


async def _scale_down_unused_cluster_instances(
    app: FastAPI,
    cluster: Cluster,
    auto_scaling_mode: AutoscalingProvider,
) -> Cluster:
    if any(not instance.has_assigned_tasks() for instance in cluster.active_nodes):
        # ask the provider to try to retire nodes actively
        with (
            log_catch(_logger, reraise=False),
            log_context(_logger, logging.INFO, "actively ask to retire unused nodes"),
        ):
            await auto_scaling_mode.try_retire_nodes(app)
    cluster = await _deactivate_empty_nodes(app, cluster)
    return await _try_scale_down_cluster(app, cluster)


async def _scale_up_cluster(
    app: FastAPI,
    cluster: Cluster,
    auto_scaling_mode: AutoscalingProvider,
    allowed_instance_types: list[EC2InstanceType],
    unassigned_tasks: list,
) -> Cluster:
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    if not unassigned_tasks and (
        len(cluster.hot_buffer_drained_nodes)
        >= app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER
    ):
        return cluster

    if (
        cluster.total_number_of_machines()
        >= app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES
    ):
        _logger.info(
            "cluster already hit the maximum allowed amount of instances (%s), not scaling up. "
            "%s tasks will wait until instances are free.",
            app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES,
            len(unassigned_tasks),
        )
        return cluster

    # now we scale up
    assert app_settings.AUTOSCALING_EC2_ACCESS  # nosec

    # let's start these
    instances_to_launch = await _find_needed_instances(
        app, unassigned_tasks, allowed_instance_types, cluster, auto_scaling_mode
    )
    if instances_to_launch:
        await post_tasks_log_message(
            app,
            tasks=unassigned_tasks,
            message="service is pending due to missing resources, scaling up cluster now...",
            level=logging.INFO,
        )
        new_pending_instances = await _launch_instances(
            app,
            instances_to_launch,
            unassigned_tasks,
            auto_scaling_mode,
        )
        cluster.pending_ec2s.extend(
            [NonAssociatedInstance(ec2_instance=i) for i in new_pending_instances]
        )
        # NOTE: to check the logs of UserData in EC2 instance
        # run: tail -f -n 1000 /var/log/cloud-init-output.log in the instance

    return cluster


async def _autoscale_cluster(
    app: FastAPI,
    cluster: Cluster,
    auto_scaling_mode: AutoscalingProvider,
    allowed_instance_types: list[EC2InstanceType],
) -> Cluster:
    # 1. check if we have pending tasks
    unnasigned_pending_tasks = await auto_scaling_mode.list_unrunnable_tasks(app)
    _logger.info(
        "found %s pending task%s",
        len(unnasigned_pending_tasks),
        "s" if len(unnasigned_pending_tasks) > 1 else "",
    )
    # NOTE: this function predicts how the backend will assign tasks
    still_pending_tasks, cluster = await _assign_tasks_to_current_cluster(
        app, unnasigned_pending_tasks, cluster, auto_scaling_mode
    )

    # 2. activate available drained nodes to cover some of the tasks
    cluster = await _activate_drained_nodes(app, cluster)

    # 3. start warm buffer instances to cover the remaining tasks
    cluster, de_assigned_tasks = await _try_start_warm_buffer_instances(
        app, cluster, auto_scaling_mode
    )
    # 3.1 if some tasks were de-assigned, we need to add them to the still pending tasks
    still_pending_tasks.extend(de_assigned_tasks)

    # 4. scale down unused instances
    cluster = await _scale_down_unused_cluster_instances(
        app, cluster, auto_scaling_mode
    )

    # 5. scale up if necessary
    return await _scale_up_cluster(
        app, cluster, auto_scaling_mode, allowed_instance_types, still_pending_tasks
    )


async def _notify_autoscaling_status(
    app: FastAPI, cluster: Cluster, auto_scaling_mode: AutoscalingProvider
) -> None:
    monitored_instances = list(
        itertools.chain(
            cluster.active_nodes,
            cluster.drained_nodes,
            cluster.hot_buffer_drained_nodes,
        )
    )

    with log_catch(_logger, reraise=False):
        (total_resources, used_resources) = await asyncio.gather(
            *(
                auto_scaling_mode.compute_cluster_total_resources(
                    app, monitored_instances
                ),
                auto_scaling_mode.compute_cluster_used_resources(
                    app, monitored_instances
                ),
            )
        )
        # inform on rabbitMQ about status
        await post_autoscaling_status_message(
            app, cluster, total_resources, used_resources
        )
        # prometheus instrumentation
        if has_instrumentation(app):
            get_instrumentation(app).cluster_metrics.update_from_cluster(cluster)


async def _handle_pre_pull_status(
    app: FastAPI, node: AssociatedInstance
) -> AssociatedInstance:
    if MACHINE_PULLING_EC2_TAG_KEY not in node.ec2_instance.tags:
        return node

    ssm_client = get_ssm_client(app)
    ec2_client = get_ec2_client(app)
    ssm_command_id = node.ec2_instance.tags.get(MACHINE_PULLING_COMMAND_ID_EC2_TAG_KEY)

    async def _remove_tags_and_return(
        node: AssociatedInstance, tag_keys: list[AWSTagKey]
    ) -> AssociatedInstance:
        await ec2_client.remove_instances_tags(
            [node.ec2_instance],
            tag_keys=tag_keys,
        )
        for tag_key in tag_keys:
            node.ec2_instance.tags.pop(tag_key, None)
        return node

    if not ssm_command_id:
        _logger.error(
            "%s has '%s' tag key set but no associated command id '%s' tag key, "
            "this is unexpected but will be cleaned now. Pre-pulling will be retried again later.",
            node.ec2_instance.id,
            MACHINE_PULLING_EC2_TAG_KEY,
            MACHINE_PULLING_COMMAND_ID_EC2_TAG_KEY,
        )
        return await _remove_tags_and_return(
            node,
            [
                MACHINE_PULLING_EC2_TAG_KEY,
                MACHINE_PULLING_COMMAND_ID_EC2_TAG_KEY,
                *list_pre_pulled_images_tag_keys(node.ec2_instance.tags),
            ],
        )

    try:
        ssm_command = await ssm_client.get_command(
            node.ec2_instance.id, command_id=ssm_command_id
        )
    except SSMAccessError as exc:
        _logger.exception(
            **create_troubleshooting_log_kwargs(
                f"Unexpected SSM access error to get status of command {ssm_command_id} on {node.ec2_instance.id}",
                error=exc,
                tip="Pre-pulling will be retried again later.",
            )
        )
        return await _remove_tags_and_return(
            node,
            [
                MACHINE_PULLING_EC2_TAG_KEY,
                MACHINE_PULLING_COMMAND_ID_EC2_TAG_KEY,
                *list_pre_pulled_images_tag_keys(node.ec2_instance.tags),
            ],
        )
    match ssm_command.status:
        case "Success":
            _logger.info("%s finished pre-pulling images", node.ec2_instance.id)
            return await _remove_tags_and_return(
                node,
                [
                    MACHINE_PULLING_EC2_TAG_KEY,
                    MACHINE_PULLING_COMMAND_ID_EC2_TAG_KEY,
                ],
            )
        case "Failed" | "TimedOut":
            _logger.error(
                "%s failed pre-pulling images, status is %s. this will be retried later",
                node.ec2_instance.id,
                ssm_command.status,
            )
            return await _remove_tags_and_return(
                node,
                [
                    MACHINE_PULLING_EC2_TAG_KEY,
                    MACHINE_PULLING_COMMAND_ID_EC2_TAG_KEY,
                    *list_pre_pulled_images_tag_keys(node.ec2_instance.tags),
                ],
            )
        case _:
            _logger.info(
                "%s is pre-pulling images, status is %s",
                node.ec2_instance.id,
                ssm_command.status,
            )
            # skip the instance this time as this is still ongoing
            return node


async def _pre_pull_docker_images_on_idle_hot_buffers(
    app: FastAPI, cluster: Cluster
) -> None:
    if not cluster.hot_buffer_drained_nodes:
        return
    ssm_client = get_ssm_client(app)
    ec2_client = get_ec2_client(app)
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    # check if we have hot buffers that need to pull images
    hot_buffer_nodes_needing_pre_pull = []
    for node in cluster.hot_buffer_drained_nodes:
        updated_node = await _handle_pre_pull_status(app, node)
        if MACHINE_PULLING_EC2_TAG_KEY in updated_node.ec2_instance.tags:
            continue  # skip this one as it is still pre-pulling

        # check what they have
        try:
            pre_pulled_images = load_pre_pulled_images_from_tags(
                updated_node.ec2_instance.tags
            )
        except Ec2TagDeserializationError as exc:
            _logger.warning(
                **create_troubleshooting_log_kwargs(
                    f"Failed to load pre-pulled images from tags for {updated_node.ec2_instance.id}, defaulting to empty list",
                    error=exc,
                    tip=f"Check the instance {node.ec2_instance.id} tags for syntax correctness. The images will be likely replaced.",
                )
            )
            pre_pulled_images = []

        ec2_boot_specific = (
            app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES[
                updated_node.ec2_instance.type
            ]
        )
        desired_pre_pulled_images = utils_docker.compute_full_list_of_pre_pulled_images(
            ec2_boot_specific, app_settings
        )

        if pre_pulled_images != desired_pre_pulled_images:
            _logger.info(
                "%s needs to pre-pull images %s, currently has %s",
                updated_node.ec2_instance.id,
                desired_pre_pulled_images,
                pre_pulled_images,
            )
            hot_buffer_nodes_needing_pre_pull.append(updated_node)

    # now trigger pre-pull on these nodes
    for node in hot_buffer_nodes_needing_pre_pull:
        ec2_boot_specific = (
            app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES[
                node.ec2_instance.type
            ]
        )
        desired_pre_pulled_images = utils_docker.compute_full_list_of_pre_pulled_images(
            ec2_boot_specific, app_settings
        )
        _logger.info(
            "triggering pre-pull of images %s on %s of type %s",
            desired_pre_pulled_images,
            node.ec2_instance.id,
            node.ec2_instance.type,
        )
        change_docker_compose_and_pull_command = " && ".join(
            (
                utils_docker.write_compose_file_command(desired_pre_pulled_images),
                DOCKER_PULL_COMMAND,
            )
        )
        ssm_command = await ssm_client.send_command(
            (node.ec2_instance.id,),
            command=change_docker_compose_and_pull_command,
            command_name=PREPULL_COMMAND_NAME,
        )
        await ec2_client.set_instances_tags(
            (node.ec2_instance,),
            tags={
                MACHINE_PULLING_EC2_TAG_KEY: "true",
                MACHINE_PULLING_COMMAND_ID_EC2_TAG_KEY: ssm_command.command_id,
            }
            | dump_pre_pulled_images_as_tags(desired_pre_pulled_images),
        )


async def auto_scale_cluster(
    *, app: FastAPI, auto_scaling_mode: AutoscalingProvider
) -> None:
    """Check that there are no pending tasks requiring additional resources in the cluster (docker swarm)
    If there are such tasks, this method will allocate new machines in AWS to cope with
    the additional load.
    """
    # current state
    allowed_instance_types = await _sorted_allowed_instance_types(
        app, auto_scaling_mode
    )

    cluster = await _analyze_current_cluster(
        app, auto_scaling_mode, allowed_instance_types
    )

    # cleanup
    cluster = await _cleanup_disconnected_nodes(app, cluster)
    cluster = await _terminate_broken_ec2s(app, cluster)
    cluster = await _make_pending_warm_buffer_ec2s_join_cluster(app, cluster)
    cluster = await _try_attach_pending_ec2s(
        app, cluster, auto_scaling_mode, allowed_instance_types
    )
    cluster = await _drain_retired_nodes(app, cluster)

    # desired state
    cluster = await _autoscale_cluster(
        app, cluster, auto_scaling_mode, allowed_instance_types
    )

    # take care of hot buffer pre-pulling
    await _pre_pull_docker_images_on_idle_hot_buffers(app, cluster)
    # notify
    await _notify_machine_creation_progress(app, cluster)
    await _notify_autoscaling_status(app, cluster, auto_scaling_mode)
