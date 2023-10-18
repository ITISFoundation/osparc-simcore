import asyncio
import collections
import dataclasses
import datetime
import itertools
import logging
from typing import cast

from fastapi import FastAPI
from models_library.generated_models.docker_rest_api import (
    Availability,
    Node,
    NodeState,
)
from pydantic import parse_obj_as
from servicelib.logging_utils import log_catch
from types_aiobotocore_ec2.literals import InstanceTypeType

from ..core.errors import (
    Ec2InstanceNotFoundError,
    Ec2InvalidDnsNameError,
    Ec2TooManyInstancesError,
)
from ..core.settings import ApplicationSettings, get_application_settings
from ..models import (
    AssociatedInstance,
    Cluster,
    EC2InstanceData,
    EC2InstanceType,
    Resources,
)
from ..utils import ec2, utils_docker
from ..utils.auto_scaling_core import (
    associate_ec2_instances_with_nodes,
    ec2_startup_script,
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
        app_settings.AUTOSCALING_EC2_INSTANCES, auto_scaling_mode.get_ec2_tags(app)
    )

    terminated_ec2_instances = await get_ec2_client(app).get_instances(
        app_settings.AUTOSCALING_EC2_INSTANCES,
        auto_scaling_mode.get_ec2_tags(app),
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
    await utils_docker.remove_nodes(get_docker_client(app), cluster.disconnected_nodes)
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
                    tags=auto_scaling_mode.get_new_node_docker_tags(app),
                    available=False,
                )
                new_found_instances.append(AssociatedInstance(new_node, instance_data))
            else:
                still_pending_ec2s.append(instance_data)
        except Ec2InvalidDnsNameError:
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
    allowed_instance_types = await ec2_client.get_ec2_instance_capabilities(
        cast(  # type: ignore
            set[InstanceTypeType],
            set(
                app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES,
            ),
        )
    )

    def _sort_according_to_allowed_types(instance_type: EC2InstanceType) -> int:
        assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
        return app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES.index(
            instance_type.name
        )

    allowed_instance_types.sort(key=_sort_according_to_allowed_types)
    return allowed_instance_types


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

    async def _activate_and_notify(
        drained_node: AssociatedInstance, tasks: list
    ) -> list:
        await asyncio.gather(
            *(
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
        )
        return tasks

    # activate these nodes now
    await asyncio.gather(
        *(_activate_and_notify(node, tasks) for node, tasks in nodes_to_activate)
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


async def _find_needed_instances(
    app: FastAPI,
    pending_tasks: list,
    available_ec2_types: list[EC2InstanceType],
    cluster: Cluster,
    auto_scaling_mode: BaseAutoscaling,
) -> dict[EC2InstanceType, int]:
    type_to_instance_map = {t.name: t for t in available_ec2_types}

    # 1. check first the pending task needs
    active_instance_to_tasks: list[tuple[EC2InstanceData, list]] = [
        (i.ec2_instance, []) for i in cluster.active_nodes
    ]
    pending_instance_to_tasks: list[tuple[EC2InstanceData, list]] = [
        (i, []) for i in cluster.pending_ec2s
    ]
    needed_new_instance_types_for_tasks: list[tuple[EC2InstanceType, list]] = []
    for task in pending_tasks:
        if await auto_scaling_mode.try_assigning_task_to_pending_instances(
            app,
            task,
            active_instance_to_tasks,
            type_to_instance_map,
            notify_progress=False,
        ):
            continue
        if await auto_scaling_mode.try_assigning_task_to_pending_instances(
            app,
            task,
            pending_instance_to_tasks,
            type_to_instance_map,
            notify_progress=True,
        ):
            continue

        if auto_scaling_mode.try_assigning_task_to_instance_types(
            task, needed_new_instance_types_for_tasks
        ):
            continue

        try:
            # we need a new instance, let's find one
            best_ec2_instance = ec2.find_best_fitting_ec2_instance(
                available_ec2_types,
                auto_scaling_mode.get_max_resources_from_task(task),
                score_type=ec2.closest_instance_policy,
            )
            needed_new_instance_types_for_tasks.append((best_ec2_instance, [task]))
        except Ec2InstanceNotFoundError:
            _logger.exception(
                "Task %s needs more resources than any EC2 instance "
                "can provide with the current configuration. Please check.",
                f"{task}",
            )

    num_instances_per_type = collections.defaultdict(
        int, collections.Counter(t for t, _ in needed_new_instance_types_for_tasks)
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
            instance
            for instance, assigned_tasks in pending_instance_to_tasks
            if not assigned_tasks
        ]
        if len(remaining_pending_instances) < (
            app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER
            - len(cluster.reserve_drained_nodes)
        ):
            default_instance_type = available_ec2_types[0]
            num_instances_per_type[default_instance_type] += num_missing_nodes

    return num_instances_per_type


async def _start_instances(
    app: FastAPI,
    needed_instances: dict[EC2InstanceType, int],
    tasks: list,
    auto_scaling_mode: BaseAutoscaling,
) -> list[EC2InstanceData]:
    ec2_client = get_ec2_client(app)
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec

    instance_tags = auto_scaling_mode.get_ec2_tags(app)
    instance_startup_script = await ec2_startup_script(app_settings)
    results = await asyncio.gather(
        *[
            ec2_client.start_aws_instance(
                app_settings.AUTOSCALING_EC2_INSTANCES,
                instance_type=parse_obj_as(InstanceTypeType, instance.name),
                tags=instance_tags,
                startup_script=instance_startup_script,
                number_of_instances=instance_num,
            )
            for instance, instance_num in needed_instances.items()
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

    log_message = f"{sum(n for n in needed_instances.values())} new machines launched, it might take up to 3 minutes to start, Please wait..."
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
    active_empty_nodes: list[AssociatedInstance] = []
    active_non_empty_nodes: list[AssociatedInstance] = []
    for instance in cluster.active_nodes:
        if (
            await auto_scaling_mode.compute_node_used_resources(
                app,
                instance,
            )
            == Resources.create_as_empty()
        ):
            active_empty_nodes.append(instance)
        else:
            active_non_empty_nodes.append(instance)

    # drain this empty nodes
    await asyncio.gather(
        *(
            utils_docker.set_node_availability(
                docker_client,
                node.node,
                available=False,
            )
            for node in active_empty_nodes
        )
    )
    if active_empty_nodes:
        _logger.info(
            "The following nodes set to drain: '%s'",
            f"{[node.node.Description.Hostname for node in active_empty_nodes if node.node.Description]}",
        )
    return dataclasses.replace(
        cluster,
        active_nodes=active_non_empty_nodes,
        drained_nodes=cluster.drained_nodes + active_empty_nodes,
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
        # NOTE: AWS price is hourly based (e.g. same price for a machine used 2 minutes or 1 hour, so we wait until 55 minutes)
        elapsed_time_since_launched = (
            datetime.datetime.now(datetime.timezone.utc)
            - instance.ec2_instance.launch_time
        )
        elapsed_time_since_full_hour = elapsed_time_since_launched % datetime.timedelta(
            hours=1
        )
        if (
            elapsed_time_since_full_hour
            >= app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
        ):
            # let's terminate that one
            terminateable_nodes.append(instance)

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
            [i.node for i in terminateable_instances],
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
    # 2. try to activate drained nodes to cover some of the tasks
    still_unrunnable_tasks, cluster = await _activate_drained_nodes(
        app, cluster, unrunnable_tasks, auto_scaling_mode
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
