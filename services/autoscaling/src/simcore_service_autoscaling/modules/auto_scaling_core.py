import asyncio
import collections
import dataclasses
import datetime
import itertools
import logging
from typing import cast

import arrow
from aws_library.ec2.models import (
    EC2InstanceConfig,
    EC2InstanceData,
    EC2InstanceType,
    EC2Tags,
    Resources,
)
from fastapi import FastAPI
from models_library.generated_models.docker_rest_api import (
    Availability,
    Node,
    NodeState,
)
from servicelib.logging_utils import log_catch
from types_aiobotocore_ec2.literals import InstanceTypeType

from ..core.errors import (
    DaskWorkerNotFoundError,
    Ec2InstanceInvalidError,
    Ec2InstanceNotFoundError,
    Ec2InvalidDnsNameError,
    Ec2TooManyInstancesError,
)
from ..core.settings import ApplicationSettings, get_application_settings
from ..models import (
    AssignedTasksToInstance,
    AssignedTasksToInstanceType,
    AssociatedInstance,
    Cluster,
)
from ..utils import utils_docker, utils_ec2
from ..utils.auto_scaling_core import (
    associate_ec2_instances_with_nodes,
    ec2_startup_script,
    filter_by_task_defined_instance,
    find_selected_instance_type_for_task,
    node_host_name_from_ec2_private_dns,
)
from ..utils.rabbitmq import post_autoscaling_status_message
from .auto_scaling_mode_base import BaseAutoscaling
from .docker import get_docker_client
from .ec2 import get_ec2_client

_logger = logging.getLogger(__name__)


async def _analyze_current_cluster(
    app: FastAPI, auto_scaling_mode: BaseAutoscaling
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

    def _is_node_up_and_available(node: Node, availability: Availability) -> bool:
        assert node.Status  # nosec
        assert node.Spec  # nosec
        return bool(
            node.Status.State == NodeState.ready
            and node.Spec.Availability == availability
        )

    def _node_not_ready(node: Node) -> bool:
        assert node.Status  # nosec
        return bool(node.Status.State != NodeState.ready)

    all_drained_nodes = [
        i
        for i in attached_ec2s
        if _is_node_up_and_available(i.node, Availability.drain)
    ]

    cluster = Cluster(
        active_nodes=[
            i
            for i in attached_ec2s
            if _is_node_up_and_available(i.node, Availability.active)
        ],
        drained_nodes=all_drained_nodes[
            app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER :
        ],
        reserve_drained_nodes=all_drained_nodes[
            : app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER
        ],
        pending_ec2s=pending_ec2s,
        terminated_instances=terminated_ec2_instances,
        disconnected_nodes=[n for n in docker_nodes if _node_not_ready(n)],
    )
    _logger.info("current state: %s", f"{cluster=}")
    return cluster


async def _cleanup_disconnected_nodes(app: FastAPI, cluster: Cluster) -> Cluster:
    if cluster.disconnected_nodes:
        await utils_docker.remove_nodes(
            get_docker_client(app), nodes=cluster.disconnected_nodes
        )
    return dataclasses.replace(cluster, disconnected_nodes=[])


async def _try_attach_pending_ec2s(
    app: FastAPI, cluster: Cluster, auto_scaling_mode: BaseAutoscaling
) -> Cluster:
    """label the drained instances that connected to the swarm which are missing the monitoring labels"""
    new_found_instances: list[AssociatedInstance] = []
    still_pending_ec2s: list[EC2InstanceData] = []
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    for instance_data in cluster.pending_ec2s:
        try:
            node_host_name = node_host_name_from_ec2_private_dns(instance_data)
            if new_node := await utils_docker.find_node_with_name(
                get_docker_client(app), node_host_name
            ):
                # it is attached, let's label it, but keep it as drained
                new_node = await utils_docker.tag_node(
                    get_docker_client(app),
                    new_node,
                    tags=auto_scaling_mode.get_new_node_docker_tags(app, instance_data),
                    available=False,
                )
                new_found_instances.append(AssociatedInstance(new_node, instance_data))
            else:
                still_pending_ec2s.append(instance_data)
        except Ec2InvalidDnsNameError:  # noqa: PERF203
            _logger.exception("Unexpected EC2 private dns")
    # NOTE: first provision the reserve drained nodes if possible
    all_drained_nodes = (
        cluster.drained_nodes + cluster.reserve_drained_nodes + new_found_instances
    )
    return dataclasses.replace(
        cluster,
        drained_nodes=all_drained_nodes[
            app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER :
        ],
        reserve_drained_nodes=all_drained_nodes[
            : app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER
        ],
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
    tasks: list,
) -> list:
    await asyncio.gather(
        utils_docker.set_node_availability(
            get_docker_client(app), drained_node.node, available=True
        ),
        auto_scaling_mode.log_message_from_tasks(
            app,
            tasks,
            "cluster adjusted, service should start shortly...",
            level=logging.INFO,
        ),
        auto_scaling_mode.progress_message_from_tasks(app, tasks, progress=1.0),
    )
    return tasks


async def _activate_drained_nodes(
    app: FastAPI,
    cluster: Cluster,
    pending_tasks: list,
    auto_scaling_mode: BaseAutoscaling,
) -> tuple[list, Cluster]:
    """returns the tasks that were assigned to the drained nodes"""
    if not pending_tasks:
        # nothing to do
        return [], cluster

    activatable_nodes: list[tuple[AssociatedInstance, list]] = [
        (
            node,
            [],
        )
        for node in itertools.chain(
            cluster.drained_nodes, cluster.reserve_drained_nodes
        )
    ]

    still_pending_tasks = [
        task
        for task in pending_tasks
        if not auto_scaling_mode.try_assigning_task_to_node(task, activatable_nodes)
    ]

    nodes_to_activate = [
        (node, assigned_tasks)
        for node, assigned_tasks in activatable_nodes
        if assigned_tasks
    ]

    # activate these nodes now
    await asyncio.gather(
        *(
            _activate_and_notify(app, auto_scaling_mode, node, tasks)
            for node, tasks in nodes_to_activate
        )
    )
    new_active_nodes = [node for node, _ in nodes_to_activate]
    new_active_node_ids = {node.ec2_instance.id for node in new_active_nodes}
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
    return still_pending_tasks, dataclasses.replace(
        cluster,
        active_nodes=cluster.active_nodes + new_active_nodes,
        drained_nodes=remaining_drained_nodes,
        reserve_drained_nodes=remaining_reserved_drained_nodes,
    )


async def _try_assign_tasks_to_instances(
    app: FastAPI,
    task,
    auto_scaling_mode: BaseAutoscaling,
    task_defined_ec2_type: InstanceTypeType | None,
    active_instances_to_tasks: list[AssignedTasksToInstance],
    pending_instances_to_tasks: list[AssignedTasksToInstance],
    drained_instances_to_tasks: list[AssignedTasksToInstance],
    needed_new_instance_types_for_tasks: list[AssignedTasksToInstanceType],
) -> bool:
    (
        filtered_active_instance_to_task,
        filtered_pending_instance_to_task,
        filtered_drained_instances_to_task,
        filtered_needed_new_instance_types_to_task,
    ) = filter_by_task_defined_instance(
        task_defined_ec2_type,
        active_instances_to_tasks,
        pending_instances_to_tasks,
        drained_instances_to_tasks,
        needed_new_instance_types_for_tasks,
    )
    # try to assign the task to one of the active, pending or net created instances
    if (
        await auto_scaling_mode.try_assigning_task_to_instances(
            app,
            task,
            filtered_active_instance_to_task,
            notify_progress=False,
        )
        or await auto_scaling_mode.try_assigning_task_to_instances(
            app,
            task,
            filtered_pending_instance_to_task,
            notify_progress=True,
        )
        or await auto_scaling_mode.try_assigning_task_to_instances(
            app,
            task,
            filtered_drained_instances_to_task,
            notify_progress=False,
        )
        or auto_scaling_mode.try_assigning_task_to_instance_types(
            task, filtered_needed_new_instance_types_to_task
        )
    ):
        return True
    return False


async def _find_needed_instances(
    app: FastAPI,
    pending_tasks: list,
    available_ec2_types: list[EC2InstanceType],
    cluster: Cluster,
    auto_scaling_mode: BaseAutoscaling,
) -> dict[EC2InstanceType, int]:
    # 1. check first the pending task needs
    active_instances_to_tasks: list[AssignedTasksToInstance] = [
        AssignedTasksToInstance(
            instance=i.ec2_instance,
            assigned_tasks=[],
            available_resources=i.ec2_instance.resources
            - await auto_scaling_mode.compute_node_used_resources(app, i),
        )
        for i in cluster.active_nodes
    ]
    pending_instances_to_tasks: list[AssignedTasksToInstance] = [
        AssignedTasksToInstance(
            instance=i, assigned_tasks=[], available_resources=i.resources
        )
        for i in cluster.pending_ec2s
    ]
    drained_instances_to_tasks: list[AssignedTasksToInstance] = [
        AssignedTasksToInstance(
            instance=i.ec2_instance,
            assigned_tasks=[],
            available_resources=i.ec2_instance.resources,
        )
        for i in cluster.drained_nodes
    ]
    needed_new_instance_types_for_tasks: list[AssignedTasksToInstanceType] = []
    for task in pending_tasks:
        task_defined_ec2_type = await auto_scaling_mode.get_task_defined_instance(
            app, task
        )
        _logger.info(
            "task %s %s",
            task,
            f"defines ec2 type as {task_defined_ec2_type}"
            if task_defined_ec2_type
            else "does NOT define ec2 type",
        )
        if await _try_assign_tasks_to_instances(
            app,
            task,
            auto_scaling_mode,
            task_defined_ec2_type,
            active_instances_to_tasks,
            pending_instances_to_tasks,
            drained_instances_to_tasks,
            needed_new_instance_types_for_tasks,
        ):
            continue

        # so we need to find what we can create now
        try:
            # check if exact instance type is needed first
            if task_defined_ec2_type:
                defined_ec2 = find_selected_instance_type_for_task(
                    task_defined_ec2_type, available_ec2_types, auto_scaling_mode, task
                )
                needed_new_instance_types_for_tasks.append(
                    AssignedTasksToInstanceType(
                        instance_type=defined_ec2, assigned_tasks=[task]
                    )
                )
            else:
                # we go for best fitting type
                best_ec2_instance = utils_ec2.find_best_fitting_ec2_instance(
                    available_ec2_types,
                    auto_scaling_mode.get_max_resources_from_task(task),
                    score_type=utils_ec2.closest_instance_policy,
                )
                needed_new_instance_types_for_tasks.append(
                    AssignedTasksToInstanceType(
                        instance_type=best_ec2_instance, assigned_tasks=[task]
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
            i.instance for i in pending_instances_to_tasks if not i.assigned_tasks
        ]
        if len(remaining_pending_instances) < (
            app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER
            - len(cluster.reserve_drained_nodes)
        ):
            default_instance_type = available_ec2_types[0]
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
                ),
                number_of_instances=instance_num,
                max_number_of_instances=app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MAX_INSTANCES,
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
        elif isinstance(r, Exception):
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
    pending_tasks: list,
    auto_scaling_mode: BaseAutoscaling,
) -> Cluster:
    app_settings: ApplicationSettings = app.state.settings
    assert app_settings.AUTOSCALING_EC2_ACCESS  # nosec
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec

    allowed_instance_types = await sorted_allowed_instance_types(app)

    # let's start these
    if needed_ec2_instances := await _find_needed_instances(
        app, pending_tasks, allowed_instance_types, cluster, auto_scaling_mode
    ):
        await auto_scaling_mode.log_message_from_tasks(
            app,
            pending_tasks,
            "service is pending due to missing resources, scaling up cluster now\n"
            f"{sum(n for n in needed_ec2_instances.values())} new machines will be added, please wait...",
            level=logging.INFO,
        )
        # NOTE: notify the up-scaling progress started...
        await auto_scaling_mode.progress_message_from_tasks(app, pending_tasks, 0.001)
        new_pending_instances = await _start_instances(
            app, needed_ec2_instances, pending_tasks, auto_scaling_mode
        )
        cluster.pending_ec2s.extend(new_pending_instances)
        # NOTE: to check the logs of UserData in EC2 instance
        # run: tail -f -n 1000 /var/log/cloud-init-output.log in the instance

    return cluster


async def _deactivate_empty_nodes(
    app: FastAPI, cluster: Cluster, auto_scaling_mode: BaseAutoscaling
) -> Cluster:
    docker_client = get_docker_client(app)
    active_empty_instances: list[AssociatedInstance] = []
    active_non_empty_instances: list[AssociatedInstance] = []
    for instance in cluster.active_nodes:
        try:
            node_used_resources = await auto_scaling_mode.compute_node_used_resources(
                app,
                instance,
            )
            if node_used_resources == Resources.create_as_empty():
                active_empty_instances.append(instance)
            else:
                active_non_empty_instances.append(instance)
        except DaskWorkerNotFoundError:  # noqa: PERF203
            _logger.exception(
                "EC2 node instance is not registered to dask-scheduler! TIP: Needs investigation"
            )

    # drain this empty nodes
    updated_nodes: list[Node] = await asyncio.gather(
        *(
            utils_docker.set_node_availability(
                docker_client,
                node.node,
                available=False,
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
        AssociatedInstance(node, instance.ec2_instance)
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
        assert instance.node.UpdatedAt  # nosec
        node_last_updated = arrow.get(instance.node.UpdatedAt).datetime
        elapsed_time_since_drained = (
            datetime.datetime.now(datetime.timezone.utc) - node_last_updated
        )
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
                f"{(app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION - elapsed_time_since_drained).total_seconds()}",
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
    # 3. we could ask on rabbit whether someone would like to keep that machine for something (like the agent for example), if that is the case, we wait another hour and ask again?
    # 4.


async def _autoscale_cluster(
    app: FastAPI, cluster: Cluster, auto_scaling_mode: BaseAutoscaling
) -> Cluster:
    # 1. check if we have pending tasks and resolve them by activating some drained nodes
    unrunnable_tasks = await auto_scaling_mode.list_unrunnable_tasks(app)
    _logger.info("found %s unrunnable tasks", len(unrunnable_tasks))
    # 2. try to activate drained nodes to cover some of the tasks
    still_unrunnable_tasks, cluster = await _activate_drained_nodes(
        app, cluster, unrunnable_tasks, auto_scaling_mode
    )
    _logger.info(
        "still %s unrunnable tasks after node activation", len(still_unrunnable_tasks)
    )

    # let's check if there are still pending tasks or if the reserve was used
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    if still_unrunnable_tasks or (
        len(cluster.reserve_drained_nodes)
        < app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER
    ):
        # yes? then scale up
        cluster = await _scale_up_cluster(
            app, cluster, still_unrunnable_tasks, auto_scaling_mode
        )
    elif still_unrunnable_tasks == unrunnable_tasks:
        # NOTE: we only scale down in case we did not just scale up. The swarm needs some time to adjust
        cluster = await _deactivate_empty_nodes(app, cluster, auto_scaling_mode)
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

    cluster = await _analyze_current_cluster(app, auto_scaling_mode)
    cluster = await _cleanup_disconnected_nodes(app, cluster)
    cluster = await _try_attach_pending_ec2s(app, cluster, auto_scaling_mode)
    cluster = await _autoscale_cluster(app, cluster, auto_scaling_mode)

    await _notify_autoscaling_status(app, cluster, auto_scaling_mode)
