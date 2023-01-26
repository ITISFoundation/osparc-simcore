import asyncio
import collections
import dataclasses
import itertools
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import cast

from fastapi import FastAPI
from models_library.generated_models.docker_rest_api import (
    Availability,
    Node,
    NodeState,
    Task,
)
from pydantic import parse_obj_as
from types_aiobotocore_ec2.literals import InstanceTypeType

from .core.errors import (
    Ec2InstanceNotFoundError,
    Ec2InvalidDnsNameError,
    Ec2TooManyInstancesError,
)
from .core.settings import ApplicationSettings, get_application_settings
from .models import AssociatedInstance, Cluster, EC2Instance, EC2InstanceData, Resources
from .modules.docker import get_docker_client
from .modules.ec2 import get_ec2_client
from .utils import ec2, utils_docker
from .utils.dynamic_scaling import (
    associate_ec2_instances_with_nodes,
    node_host_name_from_ec2_private_dns,
    try_assigning_task_to_instances,
    try_assigning_task_to_node,
    try_assigning_task_to_pending_instances,
)
from .utils.rabbitmq import (
    log_tasks_message,
    post_autoscaling_status_message,
    progress_tasks_message,
)

logger = logging.getLogger(__name__)


async def _deactivate_empty_nodes(app: FastAPI, cluster: Cluster) -> Cluster:
    app_settings: ApplicationSettings = app.state.settings
    assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec
    docker_client = get_docker_client(app)
    active_empty_nodes: list[AssociatedInstance] = []
    active_non_empty_nodes: list[AssociatedInstance] = []
    for instance in cluster.active_nodes:
        if (
            await utils_docker.compute_node_used_resources(
                docker_client,
                instance.node,
                service_labels=app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_SERVICE_LABELS,
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
        logger.info(
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
    assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec

    if not cluster.drained_nodes:
        # there is nothing to terminate here
        return []

    # get the corresponding ec2 instance data
    terminateable_nodes: list[AssociatedInstance] = []

    for instance in cluster.drained_nodes:
        # NOTE: AWS price is hourly based (e.g. same price for a machine used 2 minutes or 1 hour, so we wait until 55 minutes)
        elapsed_time_since_launched = (
            datetime.now(timezone.utc) - instance.ec2_instance.launch_time
        )
        elapsed_time_since_full_hour = elapsed_time_since_launched % timedelta(hours=1)
        if (
            elapsed_time_since_full_hour
            >= app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
        ):
            # let's terminate that one
            terminateable_nodes.append(instance)

    if terminateable_nodes:
        logger.info(
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
        logger.info(
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


async def _activate_drained_nodes(
    app: FastAPI,
    cluster: Cluster,
    pending_tasks: list[Task],
) -> tuple[list[Task], Cluster]:
    """returns the tasks that were assigned to the drained nodes"""
    if not pending_tasks:
        # nothing to do
        return [], cluster

    activatable_nodes: list[tuple[AssociatedInstance, list[Task]]] = [
        (
            node,
            [],
        )
        for node in itertools.chain(
            cluster.drained_nodes, cluster.reserve_drained_nodes
        )
    ]

    still_pending_tasks = []
    for task in pending_tasks:
        if not try_assigning_task_to_node(task, activatable_nodes):
            still_pending_tasks.append(task)

    nodes_to_activate = [
        (node, assigned_tasks)
        for node, assigned_tasks in activatable_nodes
        if assigned_tasks
    ]

    async def _activate_and_notify(
        drained_node: AssociatedInstance, tasks: list[Task]
    ) -> list[Task]:
        await asyncio.gather(
            *(
                utils_docker.set_node_availability(
                    get_docker_client(app), drained_node.node, available=True
                ),
                log_tasks_message(
                    app,
                    tasks,
                    "cluster adjusted, service should start shortly...",
                ),
                progress_tasks_message(app, tasks, progress=1.0),
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
    pending_tasks: list[Task],
    available_ec2_types: list[EC2Instance],
    cluster: Cluster,
) -> dict[EC2Instance, int]:
    type_to_instance_map = {t.name: t for t in available_ec2_types}

    # 1. check first the pending task needs
    list_of_existing_instance_to_tasks: list[tuple[EC2InstanceData, list[Task]]] = [
        (i, []) for i in cluster.pending_ec2s
    ]
    list_of_new_instance_to_tasks: list[tuple[EC2Instance, list[Task]]] = []
    for task in pending_tasks:
        if await try_assigning_task_to_pending_instances(
            app, task, list_of_existing_instance_to_tasks, type_to_instance_map
        ):
            continue

        if try_assigning_task_to_instances(task, list_of_new_instance_to_tasks):
            continue

        try:
            # we need a new instance, let's find one
            best_ec2_instance = ec2.find_best_fitting_ec2_instance(
                available_ec2_types,
                utils_docker.get_max_resources_from_docker_task(task),
                score_type=ec2.closest_instance_policy,
            )
            list_of_new_instance_to_tasks.append((best_ec2_instance, [task]))
        except Ec2InstanceNotFoundError:
            logger.error(
                "Task %s needs more resources than any EC2 instance "
                "can provide with the current configuration. Please check.",
                f"{task.Name or 'unknown task name'}:{task.ServiceID or 'unknown service ID'}",
            )

    num_instances_per_type = defaultdict(
        int, collections.Counter(t for t, _ in list_of_new_instance_to_tasks)
    )

    # 2. check the buffer needs
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    if (
        num_missing_nodes := (
            app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER
            - len(cluster.reserve_drained_nodes)
        )
        > 0
    ):
        default_instance_type = available_ec2_types[0]
        num_instances_per_type[default_instance_type] += num_missing_nodes

    return num_instances_per_type


async def _start_instances(
    app: FastAPI, needed_instances: dict[EC2Instance, int], tasks: list[Task]
) -> list[EC2InstanceData]:
    ec2_client = get_ec2_client(app)
    app_settings: ApplicationSettings = app.state.settings
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec

    startup_script = await utils_docker.get_docker_swarm_join_bash_command()

    results = await asyncio.gather(
        *(
            ec2_client.start_aws_instance(
                app_settings.AUTOSCALING_EC2_INSTANCES,
                instance_type=parse_obj_as(InstanceTypeType, instance.name),
                tags=ec2.get_ec2_tags(app_settings),
                startup_script=startup_script,
                number_of_instances=instance_num,
            )
            for instance, instance_num in needed_instances.items()
        ),
        return_exceptions=True,
    )
    # parse results
    last_issue = ""
    new_pending_instances: list[EC2InstanceData] = []
    for r in results:
        if isinstance(r, Ec2TooManyInstancesError):
            await log_tasks_message(
                app,
                tasks,
                "Exceptionally high load on computational cluster, please try again later.",
                level=logging.ERROR,
            )
        elif isinstance(r, Exception):
            logger.error("Unexpected error happened when starting EC2 instance: %s", r)
            last_issue = f"{r}"
        else:
            new_pending_instances.extend(r)

    log_message = f"{sum(n for n in needed_instances.values())} new machines launched, it might take up to 3 minutes to start, Please wait..."
    if last_issue:
        log_message += "\nUnexpected issues detected, probably due to high load, please contact support"
    await log_tasks_message(app, tasks, log_message)
    return new_pending_instances


async def _scale_up_cluster(
    app: FastAPI,
    cluster: Cluster,
    pending_tasks: list[Task],
) -> Cluster:
    app_settings: ApplicationSettings = app.state.settings
    assert app_settings.AUTOSCALING_EC2_ACCESS  # nosec
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec
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

    # let's start these
    if needed_ec2_instances := await _find_needed_instances(
        app,
        pending_tasks,
        allowed_instance_types,
        cluster,
    ):
        await log_tasks_message(
            app,
            pending_tasks,
            "service is pending due to missing resources, scaling up cluster now\n"
            f"{sum(n for n in needed_ec2_instances.values())} new machines will be added, please wait...",
        )
        new_pending_instances = await _start_instances(
            app, needed_ec2_instances, pending_tasks
        )
        cluster.pending_ec2s.extend(new_pending_instances)
        await progress_tasks_message(app, pending_tasks, 0)
    return cluster


async def _try_attach_pending_ec2s(app: FastAPI, cluster: Cluster) -> Cluster:
    """label the instances that connected to the swarm that are missing the monitoring labels"""
    newly_attached_nodes: list[AssociatedInstance] = []
    still_pending_ec2: list[EC2InstanceData] = []
    app_settings: ApplicationSettings = app.state.settings
    for instance_data in cluster.pending_ec2s:
        try:
            node_host_name = node_host_name_from_ec2_private_dns(instance_data)
            if new_node := await utils_docker.try_get_node_with_name(
                get_docker_client(app), node_host_name
            ):
                # it is attached, let's label it, but keep it as drained
                new_node = await utils_docker.tag_node(
                    get_docker_client(app),
                    new_node,
                    tags=utils_docker.get_docker_tags(app_settings),
                    available=False,
                )
                newly_attached_nodes.append(AssociatedInstance(new_node, instance_data))
            else:
                still_pending_ec2.append(instance_data)
        except Ec2InvalidDnsNameError:
            logger.exception("Unexpected EC2 private dns")
    return dataclasses.replace(
        cluster,
        drained_nodes=cluster.drained_nodes + newly_attached_nodes,
        pending_ec2s=still_pending_ec2,
    )


async def _analyze_current_cluster(app: FastAPI) -> Cluster:
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec

    # get current docker nodes (these are associated (active or drained) or disconnected)
    docker_nodes: list[Node] = await utils_docker.get_monitored_nodes(
        get_docker_client(app),
        node_labels=app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS,
    )

    # get the whatever EC2 instances we have
    existing_ec2_instances = await get_ec2_client(app).get_instances(
        app_settings.AUTOSCALING_EC2_INSTANCES,
        list(ec2.get_ec2_tags(app_settings).keys()),
    )

    terminated_ec2_instances = await get_ec2_client(app).get_instances(
        app_settings.AUTOSCALING_EC2_INSTANCES,
        list(ec2.get_ec2_tags(app_settings).keys()),
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
    logger.info("current state: %s", f"{cluster=}")
    return cluster


async def _scale_cluster(app: FastAPI, cluster: Cluster) -> Cluster:
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    # 1. check if we have pending tasks and resolve them by activating some drained nodes
    pending_tasks = await utils_docker.pending_service_tasks_with_insufficient_resources(
        get_docker_client(app),
        service_labels=app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_SERVICE_LABELS,
    )
    # we have a number of pending tasks, try to resolve them with drained nodes if possible
    still_pending_tasks, cluster = await _activate_drained_nodes(
        app, cluster, pending_tasks
    )
    # let's check if there are still pending tasks or if the reserve was used
    if still_pending_tasks or (
        len(cluster.reserve_drained_nodes)
        < app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER
    ):
        # yes? then scale up
        cluster = await _scale_up_cluster(app, cluster, still_pending_tasks)
    elif still_pending_tasks == pending_tasks:
        # NOTE: we only scale down in case we did not just scale up. The swarm needs some time to adjust
        cluster = await _deactivate_empty_nodes(app, cluster)
        cluster = await _try_scale_down_cluster(app, cluster)

    return cluster


async def cluster_scaling_from_labelled_services(app: FastAPI) -> None:
    """Check that there are no pending tasks requiring additional resources in the cluster (docker swarm)
    If there are such tasks, this method will allocate new machines in AWS to cope with
    the additional load.
    """

    # 1. Analyze cluster current state
    cluster = await _analyze_current_cluster(app)

    # 2. Cleanup nodes that are gone or were terminated
    await utils_docker.remove_nodes(get_docker_client(app), cluster.disconnected_nodes)
    cluster.disconnected_nodes.clear()

    # 3. Attach/Label new connected instances
    cluster = await _try_attach_pending_ec2s(app, cluster)

    # 4. Scale the cluster
    cluster = await _scale_cluster(app, cluster)

    # 4. Notify anyone interested of current state
    await post_autoscaling_status_message(app, cluster)
