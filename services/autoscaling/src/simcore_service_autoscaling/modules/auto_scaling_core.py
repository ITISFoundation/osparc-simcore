import asyncio
import collections
import dataclasses
import datetime
import itertools
import json
import logging
from typing import Final, cast

import arrow
from aws_library.ec2.models import (
    EC2InstanceConfig,
    EC2InstanceData,
    EC2InstanceType,
    EC2Tags,
    Resources,
)
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from models_library.generated_models.docker_rest_api import Node, NodeState
from servicelib.logging_utils import log_catch, log_context
from servicelib.utils_formatting import timedelta_as_minute_second
from types_aiobotocore_ec2.literals import InstanceTypeType

from ..core.errors import (
    Ec2InstanceInvalidError,
    Ec2InstanceNotFoundError,
    Ec2InvalidDnsNameError,
    Ec2TooManyInstancesError,
)
from ..core.settings import ApplicationSettings, get_application_settings
from ..models import (
    AssignedTasksToInstanceType,
    AssociatedInstance,
    Cluster,
    NonAssociatedInstance,
)
from ..utils import utils_docker, utils_ec2
from ..utils.auto_scaling_core import (
    associate_ec2_instances_with_nodes,
    ec2_startup_script,
    find_selected_instance_type_for_task,
    get_machine_buffer_type,
    node_host_name_from_ec2_private_dns,
    sort_drained_nodes,
)
from ..utils.rabbitmq import post_autoscaling_status_message
from .auto_scaling_mode_base import BaseAutoscaling
from .docker import get_docker_client
from .ec2 import get_ec2_client

_logger = logging.getLogger(__name__)


def _node_not_ready(node: Node) -> bool:
    assert node.Status  # nosec
    return bool(node.Status.State != NodeState.ready)


async def _analyze_current_cluster(
    app: FastAPI,
    auto_scaling_mode: BaseAutoscaling,
    allowed_instance_types: list[EC2InstanceType],
) -> Cluster:
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec

    # get current docker nodes (these are associated (active or drained) or disconnected)
    docker_nodes: list[Node] = await auto_scaling_mode.get_monitored_nodes(app)

    # get the EC2 instances we have
    existing_ec2_instances = await get_ec2_client(app).get_instances(
        key_names=[app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_KEY_NAME],
        tags=auto_scaling_mode.get_ec2_tags(app),
    )

    terminated_ec2_instances = await get_ec2_client(app).get_instances(
        key_names=[app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_KEY_NAME],
        tags=auto_scaling_mode.get_ec2_tags(app),
        state_names=["terminated"],
    )

    attached_ec2s, pending_ec2s = await associate_ec2_instances_with_nodes(
        docker_nodes, existing_ec2_instances
    )

    # analyse attached ec2s
    active_nodes, pending_nodes, all_drained_nodes = [], [], []
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
        elif auto_scaling_mode.is_instance_drained(instance):
            all_drained_nodes.append(instance)
        else:
            pending_nodes.append(instance)

    drained_nodes, reserve_drained_nodes = sort_drained_nodes(
        app_settings, all_drained_nodes, allowed_instance_types
    )
    cluster = Cluster(
        active_nodes=active_nodes,
        pending_nodes=pending_nodes,
        drained_nodes=drained_nodes,
        reserve_drained_nodes=reserve_drained_nodes,
        pending_ec2s=[NonAssociatedInstance(ec2_instance=i) for i in pending_ec2s],
        terminated_instances=terminated_ec2_instances,
        disconnected_nodes=[n for n in docker_nodes if _node_not_ready(n)],
    )
    cluster_state = jsonable_encoder(
        cluster,
        include={
            "active_nodes": True,
            "pending_nodes": True,
            "drained_nodes": "available_resources",
            "reserve_drained_nodes": True,
            "pending_ec2s": "ec2_instance",
        },
    )
    _logger.info(
        "current state: %s",
        f"{json.dumps(cluster_state, indent=2)}",
    )
    return cluster


_DELAY_FOR_REMOVING_DISCONNECTED_NODES_S: Final[int] = 30


async def _cleanup_disconnected_nodes(app: FastAPI, cluster: Cluster) -> Cluster:
    utc_now = arrow.utcnow().datetime
    removeable_nodes = [
        node
        for node in cluster.disconnected_nodes
        if node.UpdatedAt
        and (
            (utc_now - arrow.get(node.UpdatedAt).datetime).total_seconds()
            > _DELAY_FOR_REMOVING_DISCONNECTED_NODES_S
        )
    ]
    if removeable_nodes:
        await utils_docker.remove_nodes(get_docker_client(app), nodes=removeable_nodes)
    return dataclasses.replace(cluster, disconnected_nodes=[])


async def _try_attach_pending_ec2s(
    app: FastAPI,
    cluster: Cluster,
    auto_scaling_mode: BaseAutoscaling,
    allowed_instance_types: list[EC2InstanceType],
) -> Cluster:
    """label the drained instances that connected to the swarm which are missing the monitoring labels"""
    new_found_instances: list[AssociatedInstance] = []
    still_pending_ec2s: list[NonAssociatedInstance] = []
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    for instance_data in cluster.pending_ec2s:
        try:
            node_host_name = node_host_name_from_ec2_private_dns(
                instance_data.ec2_instance
            )
            if new_node := await utils_docker.find_node_with_name(
                get_docker_client(app), node_host_name
            ):
                # it is attached, let's label it
                new_node = await utils_docker.attach_node(
                    app_settings,
                    get_docker_client(app),
                    new_node,
                    tags=auto_scaling_mode.get_new_node_docker_tags(
                        app, instance_data.ec2_instance
                    ),
                )
                new_found_instances.append(
                    AssociatedInstance(
                        node=new_node, ec2_instance=instance_data.ec2_instance
                    )
                )
                _logger.info(
                    "Attached new EC2 instance %s", instance_data.ec2_instance.id
                )
            else:
                still_pending_ec2s.append(instance_data)
        except Ec2InvalidDnsNameError:  # noqa: PERF203
            _logger.exception("Unexpected EC2 private dns")
    # NOTE: first provision the reserve drained nodes if possible
    all_drained_nodes = (
        cluster.drained_nodes + cluster.reserve_drained_nodes + new_found_instances
    )
    drained_nodes, reserve_drained_nodes = sort_drained_nodes(
        app_settings, all_drained_nodes, allowed_instance_types
    )
    return dataclasses.replace(
        cluster,
        drained_nodes=drained_nodes,
        reserve_drained_nodes=reserve_drained_nodes,
        pending_ec2s=still_pending_ec2s,
    )


async def sorted_allowed_instance_types(app: FastAPI) -> list[EC2InstanceType]:
    app_settings: ApplicationSettings = app.state.settings
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    ec2_client = get_ec2_client(app)

    # some instances might be able to run several tasks
    allowed_instance_types: list[
        EC2InstanceType
    ] = await ec2_client.get_ec2_instance_capabilities(
        cast(  # type: ignore
            set[InstanceTypeType],
            set(
                app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES,
            ),
        )
    )

    def _sort_according_to_allowed_types(instance_type: EC2InstanceType) -> int:
        assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
        return list(
            app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES
        ).index(f"{instance_type.name}")

    allowed_instance_types.sort(key=_sort_according_to_allowed_types)
    return allowed_instance_types


async def _activate_and_notify(
    app: FastAPI,
    auto_scaling_mode: BaseAutoscaling,
    drained_node: AssociatedInstance,
) -> None:
    app_settings = get_application_settings(app)
    docker_client = get_docker_client(app)
    await asyncio.gather(
        utils_docker.set_node_osparc_ready(
            app_settings, docker_client, drained_node.node, ready=True
        ),
        auto_scaling_mode.log_message_from_tasks(
            app,
            drained_node.assigned_tasks,
            "cluster adjusted, service should start shortly...",
            level=logging.INFO,
        ),
        auto_scaling_mode.progress_message_from_tasks(
            app, drained_node.assigned_tasks, progress=1.0
        ),
    )


async def _activate_drained_nodes(
    app: FastAPI,
    cluster: Cluster,
    auto_scaling_mode: BaseAutoscaling,
) -> Cluster:
    nodes_to_activate = [
        node
        for node in itertools.chain(
            cluster.drained_nodes, cluster.reserve_drained_nodes
        )
        if node.assigned_tasks
    ]

    # activate these nodes now
    await asyncio.gather(
        *(
            _activate_and_notify(app, auto_scaling_mode, node)
            for node in nodes_to_activate
        )
    )
    new_active_node_ids = {node.ec2_instance.id for node in nodes_to_activate}
    remaining_drained_nodes = [
        node
        for node in cluster.drained_nodes
        if node.ec2_instance.id not in new_active_node_ids
    ]
    remaining_reserved_drained_nodes = [
        node
        for node in cluster.reserve_drained_nodes
        if node.ec2_instance.id not in new_active_node_ids
    ]
    return dataclasses.replace(
        cluster,
        active_nodes=cluster.active_nodes + nodes_to_activate,
        drained_nodes=remaining_drained_nodes,
        reserve_drained_nodes=remaining_reserved_drained_nodes,
    )


def _try_assign_task_to_ec2_instance(
    task,
    *,
    instances: list[AssociatedInstance] | list[NonAssociatedInstance],
    task_required_ec2_instance: InstanceTypeType | None,
    task_required_resources: Resources,
) -> bool:
    for instance in instances:
        if task_required_ec2_instance and (
            task_required_ec2_instance != instance.ec2_instance.type
        ):
            continue
        if instance.has_resources_for_task(task_required_resources):
            instance.assign_task(task, task_required_resources)
            _logger.debug(
                "%s",
                f"assigned task with {task_required_resources=}, {task_required_ec2_instance=} to "
                f"{instance.ec2_instance.id=}:{instance.ec2_instance.type}, "
                f"remaining resources:{instance.available_resources}/{instance.ec2_instance.resources}",
            )
            return True
    return False


def _try_assign_task_to_ec2_instance_type(
    task,
    *,
    instances: list[AssignedTasksToInstanceType],
    task_required_ec2_instance: InstanceTypeType | None,
    task_required_resources: Resources,
) -> bool:
    for instance in instances:
        if task_required_ec2_instance and (
            task_required_ec2_instance != instance.instance_type.name
        ):
            continue
        if instance.has_resources_for_task(task_required_resources):
            instance.assign_task(task, task_required_resources)
            _logger.debug(
                "%s",
                f"assigned task with {task_required_resources=}, {task_required_ec2_instance=} to "
                f"{instance.instance_type}, "
                f"remaining resources:{instance.available_resources}/{instance.instance_type.resources}",
            )
            return True
    return False


async def _assign_tasks_to_current_cluster(
    app: FastAPI,
    tasks: list,
    cluster: Cluster,
    auto_scaling_mode: BaseAutoscaling,
) -> tuple[list, Cluster]:
    unassigned_tasks = []
    for task in tasks:
        task_required_resources = auto_scaling_mode.get_task_required_resources(task)
        task_required_ec2_instance = await auto_scaling_mode.get_task_defined_instance(
            app, task
        )

        assignment_functions = [
            lambda task, required_ec2, required_resources: _try_assign_task_to_ec2_instance(
                task,
                instances=cluster.active_nodes,
                task_required_ec2_instance=required_ec2,
                task_required_resources=required_resources,
            ),
            lambda task, required_ec2, required_resources: _try_assign_task_to_ec2_instance(
                task,
                instances=cluster.drained_nodes + cluster.reserve_drained_nodes,
                task_required_ec2_instance=required_ec2,
                task_required_resources=required_resources,
            ),
            lambda task, required_ec2, required_resources: _try_assign_task_to_ec2_instance(
                task,
                instances=cluster.pending_nodes,
                task_required_ec2_instance=required_ec2,
                task_required_resources=required_resources,
            ),
            lambda task, required_ec2, required_resources: _try_assign_task_to_ec2_instance(
                task,
                instances=cluster.pending_ec2s,
                task_required_ec2_instance=required_ec2,
                task_required_resources=required_resources,
            ),
        ]

        if any(
            assignment(task, task_required_ec2_instance, task_required_resources)
            for assignment in assignment_functions
        ):
            _logger.debug("assigned task to cluster")
        else:
            unassigned_tasks.append(task)

    if unassigned_tasks:
        _logger.info(
            "the current cluster should cope with %s tasks, %s are unnassigned/queued tasks",
            len(tasks) - len(unassigned_tasks),
            len(unassigned_tasks),
        )
    return unassigned_tasks, cluster


async def _find_needed_instances(
    app: FastAPI,
    unassigned_tasks: list,
    available_ec2_types: list[EC2InstanceType],
    cluster: Cluster,
    auto_scaling_mode: BaseAutoscaling,
) -> dict[EC2InstanceType, int]:
    # 1. check first the pending task needs
    needed_new_instance_types_for_tasks: list[AssignedTasksToInstanceType] = []
    with log_context(_logger, logging.DEBUG, msg="finding needed instances"):
        for task in unassigned_tasks:
            task_required_resources = auto_scaling_mode.get_task_required_resources(
                task
            )
            task_required_ec2_instance = (
                await auto_scaling_mode.get_task_defined_instance(app, task)
            )

            # first check if we can assign the task to one of the newly tobe created instances
            if _try_assign_task_to_ec2_instance_type(
                task,
                instances=needed_new_instance_types_for_tasks,
                task_required_ec2_instance=task_required_ec2_instance,
                task_required_resources=task_required_resources,
            ):
                continue

            # so we need to find what we can create now
            try:
                # check if exact instance type is needed first
                if task_required_ec2_instance:
                    defined_ec2 = find_selected_instance_type_for_task(
                        task_required_ec2_instance,
                        available_ec2_types,
                        auto_scaling_mode,
                        task,
                    )
                    needed_new_instance_types_for_tasks.append(
                        AssignedTasksToInstanceType(
                            instance_type=defined_ec2,
                            assigned_tasks=[task],
                            available_resources=defined_ec2.resources
                            - task_required_resources,
                        )
                    )
                else:
                    # we go for best fitting type
                    best_ec2_instance = utils_ec2.find_best_fitting_ec2_instance(
                        available_ec2_types,
                        auto_scaling_mode.get_task_required_resources(task),
                        score_type=utils_ec2.closest_instance_policy,
                    )
                    needed_new_instance_types_for_tasks.append(
                        AssignedTasksToInstanceType(
                            instance_type=best_ec2_instance,
                            assigned_tasks=[task],
                            available_resources=best_ec2_instance.resources
                            - task_required_resources,
                        )
                    )
            except Ec2InstanceNotFoundError:
                _logger.exception(
                    "Task %s needs more resources than any EC2 instance "
                    "can provide with the current configuration. Please check!",
                    f"{task}",
                )
            except Ec2InstanceInvalidError:
                _logger.exception("Unexpected error:")

    _logger.info(
        "found following needed instances: %s",
        [
            f"{i.instance_type.name=}:{i.instance_type.resources} with {len(i.assigned_tasks)} tasks"
            for i in needed_new_instance_types_for_tasks
        ],
    )

    num_instances_per_type = collections.defaultdict(
        int,
        collections.Counter(
            t.instance_type for t in needed_new_instance_types_for_tasks
        ),
    )

    # 2. check the buffer needs
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    if (
        num_missing_nodes := (
            app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER
            - len(cluster.reserve_drained_nodes)
        )
    ) > 0:
        # check if some are already pending
        remaining_pending_instances = [
            i.ec2_instance for i in cluster.pending_ec2s if not i.assigned_tasks
        ] + [i.ec2_instance for i in cluster.pending_nodes if not i.assigned_tasks]
        if len(remaining_pending_instances) < (
            app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER
            - len(cluster.reserve_drained_nodes)
        ):
            default_instance_type = get_machine_buffer_type(available_ec2_types)
            num_instances_per_type[default_instance_type] += num_missing_nodes

    return num_instances_per_type


async def _cap_needed_instances(
    app: FastAPI, needed_instances: dict[EC2InstanceType, int], ec2_tags: EC2Tags
) -> dict[EC2InstanceType, int]:
    """caps the needed instances dict[EC2InstanceType, int] to the maximal allowed number of instances by
    1. limiting to 1 per asked type
    2. increasing each by 1 until the maximum allowed number of instances is reached
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
    if (
        current_number_of_instances
        >= app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES
    ):
        # ok that is already too much
        raise Ec2TooManyInstancesError(
            num_instances=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES
        )

    total_number_of_needed_instances = sum(needed_instances.values())
    if (
        current_number_of_instances + total_number_of_needed_instances
        <= app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES
    ):
        # ok that fits no need to do anything here
        return needed_instances

    # this is asking for too many, so let's cap them
    max_number_of_creatable_instances = (
        app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES
        - current_number_of_instances
    )

    # we start with 1 machine of each type until the max
    capped_needed_instances = {
        k: 1
        for count, k in enumerate(needed_instances)
        if (count + 1) <= max_number_of_creatable_instances
    }

    if len(capped_needed_instances) < len(needed_instances):
        # there were too many types for the number of possible instances
        return capped_needed_instances

    # all instance types were added, now create more of them if possible
    while sum(capped_needed_instances.values()) < max_number_of_creatable_instances:
        for instance_type, num_to_create in needed_instances.items():
            if (
                sum(capped_needed_instances.values())
                == max_number_of_creatable_instances
            ):
                break
            if num_to_create > capped_needed_instances[instance_type]:
                capped_needed_instances[instance_type] += 1

    return capped_needed_instances


async def _start_instances(
    app: FastAPI,
    needed_instances: dict[EC2InstanceType, int],
    tasks: list,
    auto_scaling_mode: BaseAutoscaling,
) -> list[EC2InstanceData]:
    ec2_client = get_ec2_client(app)
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    new_instance_tags = (
        auto_scaling_mode.get_ec2_tags(app)
        | app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_CUSTOM_TAGS
    )
    capped_needed_machines = {}
    try:
        capped_needed_machines = await _cap_needed_instances(
            app, needed_instances, new_instance_tags
        )
    except Ec2TooManyInstancesError:
        await auto_scaling_mode.log_message_from_tasks(
            app,
            tasks,
            "The maximum number of machines in the cluster was reached. Please wait for your running jobs "
            "to complete and try again later or contact osparc support if this issue does not resolve.",
            level=logging.ERROR,
        )
        return []

    results = await asyncio.gather(
        *[
            ec2_client.start_aws_instance(
                EC2InstanceConfig(
                    type=instance_type,
                    tags=new_instance_tags,
                    startup_script=await ec2_startup_script(
                        app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES[
                            instance_type.name
                        ],
                        app_settings,
                    ),
                    ami_id=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES[
                        instance_type.name
                    ].ami_id,
                    key_name=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_KEY_NAME,
                    security_group_ids=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_SECURITY_GROUP_IDS,
                    subnet_id=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_SUBNET_ID,
                    iam_instance_profile="",
                ),
                min_number_of_instances=1,  # NOTE: we want at least 1 if possible
                number_of_instances=instance_num,
                max_total_number_of_instances=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES,
            )
            for instance_type, instance_num in capped_needed_machines.items()
        ],
        return_exceptions=True,
    )
    # parse results
    last_issue = ""
    new_pending_instances: list[EC2InstanceData] = []
    for r in results:
        if isinstance(r, Ec2TooManyInstancesError):
            await auto_scaling_mode.log_message_from_tasks(
                app,
                tasks,
                "Exceptionally high load on computational cluster, please try again later.",
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
        f"{sum(n for n in capped_needed_machines.values())} new machines launched"
        ", it might take up to 3 minutes to start, Please wait..."
    )
    await auto_scaling_mode.log_message_from_tasks(
        app, tasks, log_message, level=logging.INFO
    )
    if last_issue:
        await auto_scaling_mode.log_message_from_tasks(
            app,
            tasks,
            "Unexpected issues detected, probably due to high load, please contact support",
            level=logging.ERROR,
        )

    return new_pending_instances


async def _scale_up_cluster(
    app: FastAPI,
    cluster: Cluster,
    unassigned_tasks: list,
    auto_scaling_mode: BaseAutoscaling,
    allowed_instance_types: list[EC2InstanceType],
) -> Cluster:
    app_settings: ApplicationSettings = app.state.settings
    assert app_settings.AUTOSCALING_EC2_ACCESS  # nosec
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec

    # let's start these
    if needed_ec2_instances := await _find_needed_instances(
        app, unassigned_tasks, allowed_instance_types, cluster, auto_scaling_mode
    ):
        await auto_scaling_mode.log_message_from_tasks(
            app,
            unassigned_tasks,
            "service is pending due to missing resources, scaling up cluster now...",
            level=logging.INFO,
        )
        new_pending_instances = await _start_instances(
            app, needed_ec2_instances, unassigned_tasks, auto_scaling_mode
        )
        cluster.pending_ec2s.extend(
            [NonAssociatedInstance(ec2_instance=i) for i in new_pending_instances]
        )
        # NOTE: to check the logs of UserData in EC2 instance
        # run: tail -f -n 1000 /var/log/cloud-init-output.log in the instance

    return cluster


async def _deactivate_empty_nodes(app: FastAPI, cluster: Cluster) -> Cluster:
    app_settings = get_application_settings(app)
    docker_client = get_docker_client(app)
    active_empty_instances: list[AssociatedInstance] = []
    active_non_empty_instances: list[AssociatedInstance] = []
    for instance in cluster.active_nodes:
        if instance.available_resources == instance.ec2_instance.resources:
            active_empty_instances.append(instance)
        else:
            active_non_empty_instances.append(instance)

    if not active_empty_instances:
        return cluster
    _logger.info(
        "following nodes will be drained: '%s'",
        f"{[instance.node.Description.Hostname for instance in active_empty_instances if instance.node.Description]}",
    )
    # drain this empty nodes
    updated_nodes: list[Node] = await asyncio.gather(
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
            "following nodes set to drain: '%s'",
            f"{[node.Description.Hostname for node in updated_nodes if node.Description]}",
        )
    newly_drained_instances = [
        AssociatedInstance(node=node, ec2_instance=instance.ec2_instance)
        for instance, node in zip(active_empty_instances, updated_nodes, strict=True)
    ]
    return dataclasses.replace(
        cluster,
        active_nodes=active_non_empty_instances,
        drained_nodes=cluster.drained_nodes + newly_drained_instances,
    )


async def _find_terminateable_instances(
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
        node_last_updated = utils_docker.get_node_last_readyness_update(instance.node)
        elapsed_time_since_drained = (
            datetime.datetime.now(datetime.timezone.utc) - node_last_updated
        )
        _logger.warning("%s", f"{node_last_updated=}, {elapsed_time_since_drained=}")
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
            f"{[instance.node.Description.Hostname for instance in terminateable_nodes if instance.node.Description]}",
        )
    return terminateable_nodes


async def _try_scale_down_cluster(app: FastAPI, cluster: Cluster) -> Cluster:
    # 2. once it is in draining mode and we are nearing a modulo of an hour we can start the termination procedure
    # NOTE: the nodes that were just changed to drain above will be eventually terminated on the next iteration
    terminated_instance_ids = []
    if terminateable_instances := await _find_terminateable_instances(app, cluster):
        await get_ec2_client(app).terminate_instances(
            [i.ec2_instance for i in terminateable_instances]
        )
        _logger.info(
            "EC2 terminated: '%s'",
            f"{[i.node.Description.Hostname for i in terminateable_instances if i.node.Description]}",
        )
        # since these nodes are being terminated, remove them from the swarm

        await utils_docker.remove_nodes(
            get_docker_client(app),
            nodes=[i.node for i in terminateable_instances],
            force=True,
        )
        terminated_instance_ids = [i.ec2_instance.id for i in terminateable_instances]

    still_drained_nodes = [
        i
        for i in cluster.drained_nodes
        if i.ec2_instance.id not in terminated_instance_ids
    ]
    return dataclasses.replace(
        cluster,
        drained_nodes=still_drained_nodes,
        terminated_instances=cluster.terminated_instances
        + [i.ec2_instance for i in terminateable_instances],
    )


async def _notify_based_on_machine_type(
    app: FastAPI,
    instances: list[AssociatedInstance] | list[NonAssociatedInstance],
    auto_scaling_mode: BaseAutoscaling,
    *,
    message: str,
) -> None:
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    instance_max_time_to_start = (
        app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_START_TIME
    )
    launch_time_to_tasks: dict[datetime.datetime, list] = collections.defaultdict(list)
    now = datetime.datetime.now(datetime.timezone.utc)
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
            await auto_scaling_mode.log_message_from_tasks(
                app, tasks, message=msg, level=logging.INFO
            )
            await auto_scaling_mode.progress_message_from_tasks(
                app,
                tasks,
                progress=time_since_launch.total_seconds()
                / instance_max_time_to_start.total_seconds(),
            )


async def _notify_machine_creation_progress(
    app: FastAPI, cluster: Cluster, auto_scaling_mode: BaseAutoscaling
) -> None:
    await _notify_based_on_machine_type(
        app,
        cluster.pending_ec2s,
        auto_scaling_mode,
        message="waiting for machine to join cluster",
    )


async def _autoscale_cluster(
    app: FastAPI,
    cluster: Cluster,
    auto_scaling_mode: BaseAutoscaling,
    allowed_instance_types: list[EC2InstanceType],
) -> Cluster:
    # 1. check if we have pending tasks and resolve them by activating some drained nodes
    unrunnable_tasks = await auto_scaling_mode.list_unrunnable_tasks(app)
    _logger.info("found %s unrunnable tasks", len(unrunnable_tasks))

    queued_or_missing_instance_tasks, cluster = await _assign_tasks_to_current_cluster(
        app, unrunnable_tasks, cluster, auto_scaling_mode
    )
    # 2. try to activate drained nodes to cover some of the tasks
    cluster = await _activate_drained_nodes(app, cluster, auto_scaling_mode)

    # let's check if there are still pending tasks or if the reserve was used
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    if queued_or_missing_instance_tasks or (
        len(cluster.reserve_drained_nodes)
        < app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER
    ):
        if (
            cluster.total_number_of_machines()
            < app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES
        ):
            _logger.info(
                "%s unrunnable tasks could not be assigned, slowly trying to scale up...",
                len(queued_or_missing_instance_tasks),
            )
            cluster = await _scale_up_cluster(
                app,
                cluster,
                queued_or_missing_instance_tasks,
                auto_scaling_mode,
                allowed_instance_types,
            )

    elif (
        len(queued_or_missing_instance_tasks) == len(unrunnable_tasks) == 0
        and cluster.can_scale_down()
    ):
        _logger.info(
            "there is %s waiting task, slowly and gracefully scaling down...",
            len(queued_or_missing_instance_tasks),
        )
        # NOTE: we only scale down in case we did not just scale up. The swarm needs some time to adjust
        await auto_scaling_mode.try_retire_nodes(app)
        cluster = await _deactivate_empty_nodes(app, cluster)
        cluster = await _try_scale_down_cluster(app, cluster)

    return cluster


async def _notify_autoscaling_status(
    app: FastAPI, cluster: Cluster, auto_scaling_mode: BaseAutoscaling
) -> None:
    # inform on rabbit about status
    monitored_instances = list(
        itertools.chain(
            cluster.active_nodes, cluster.drained_nodes, cluster.reserve_drained_nodes
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
        await post_autoscaling_status_message(
            app, cluster, total_resources, used_resources
        )


async def auto_scale_cluster(
    *, app: FastAPI, auto_scaling_mode: BaseAutoscaling
) -> None:
    """Check that there are no pending tasks requiring additional resources in the cluster (docker swarm)
    If there are such tasks, this method will allocate new machines in AWS to cope with
    the additional load.
    """

    allowed_instance_types = await sorted_allowed_instance_types(app)
    cluster = await _analyze_current_cluster(
        app, auto_scaling_mode, allowed_instance_types
    )
    cluster = await _cleanup_disconnected_nodes(app, cluster)
    cluster = await _try_attach_pending_ec2s(
        app, cluster, auto_scaling_mode, allowed_instance_types
    )

    cluster = await _autoscale_cluster(
        app, cluster, auto_scaling_mode, allowed_instance_types
    )
    await _notify_machine_creation_progress(app, cluster, auto_scaling_mode)
    await _notify_autoscaling_status(app, cluster, auto_scaling_mode)
