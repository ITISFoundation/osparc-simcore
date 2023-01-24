import asyncio
import collections
import itertools
import logging
from datetime import datetime, timedelta, timezone
from typing import cast

from fastapi import FastAPI
from models_library.generated_models.docker_rest_api import Availability, Node, Task
from pydantic import parse_obj_as
from types_aiobotocore_ec2.literals import InstanceTypeType

from .core.errors import (
    Ec2InstanceNotFoundError,
    Ec2InvalidDnsNameError,
    Ec2TooManyInstancesError,
)
from .core.settings import ApplicationSettings
from .models import AssociatedInstance, EC2Instance, EC2InstanceData, Resources
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


async def _deactivate_empty_nodes(
    app: FastAPI,
    attached_ec2s: list[AssociatedInstance],
) -> None:
    app_settings: ApplicationSettings = app.state.settings
    assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec
    docker_client = get_docker_client(app)
    active_empty_nodes = [
        instance.node
        for instance in attached_ec2s
        if (
            await utils_docker.compute_node_used_resources(
                docker_client,
                instance.node,
                service_labels=app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_SERVICE_LABELS,
            )
            == Resources.create_as_empty()
        )
        and (instance.node.Spec is not None)
        and (instance.node.Spec.Availability == Availability.active)
    ]
    await asyncio.gather(
        *(
            utils_docker.set_node_availability(
                docker_client,
                node,
                available=False,
            )
            for node in active_empty_nodes
            if (node.Spec) and (node.Spec.Labels is not None)
        )
    )
    if active_empty_nodes:
        logger.info(
            "The following nodes set to drain: '%s'",
            f"{[node.Description.Hostname for node in active_empty_nodes if node.Description]}",
        )


async def _find_terminateable_instances(
    app: FastAPI, attached_ec2s: list[AssociatedInstance]
) -> list[AssociatedInstance]:
    app_settings: ApplicationSettings = app.state.settings
    assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec

    # NOTE: we want the drained nodes where no monitored service is running anymore
    drained_empty_instances = await utils_docker.get_drained_empty_nodes(
        get_docker_client(app), app_settings, attached_ec2s
    )

    # we keep a buffer of nodes always on the ready
    drained_empty_instances = drained_empty_instances[
        app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER :
    ]

    if not drained_empty_instances:
        # there is nothing to terminate here
        return []

    # get the corresponding ec2 instance data
    terminateable_nodes: list[AssociatedInstance] = []

    for instance in drained_empty_instances:
        # NOTE: AWS price is hourly based (e.g. same price for a machine used 2 minutes or 1 hour, so we wait until 55 minutes)
        elapsed_time_since_launched = (
            datetime.utcnow().replace(tzinfo=timezone.utc)
            - instance.ec2_instance.launch_time
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


async def _try_scale_down_cluster(
    app: FastAPI, attached_ec2s: list[AssociatedInstance]
) -> None:
    # 2. once it is in draining mode and we are nearing a modulo of an hour we can start the termination procedure
    # NOTE: the nodes that were just changed to drain above will be eventually terminated on the next iteration
    if terminateable_instances := await _find_terminateable_instances(
        app, attached_ec2s
    ):
        await get_ec2_client(app).terminate_instances(
            [i.ec2_instance for i in terminateable_instances]
        )
        logger.info(
            "terminated the following machines: '%s'",
            f"{[i.node.Description.Hostname for i in terminateable_instances if i.node.Description]}",
        )
        # since these nodes are being terminated, remove them from the swarm
        await utils_docker.remove_nodes(
            get_docker_client(app),
            [i.node for i in terminateable_instances],
            force=True,
        )

    # 3. we could ask on rabbit whether someone would like to keep that machine for something (like the agent for example), if that is the case, we wait another hour and ask again?
    # 4.


async def _activate_drained_nodes(
    app: FastAPI,
    associated_instances: list[AssociatedInstance],
    pending_tasks: list[Task],
) -> list[Task]:
    """returns the tasks that were assigned to the drained nodes"""
    docker_client = get_docker_client(app)
    if not pending_tasks:
        return []

    activatable_nodes: list[tuple[Node, list[Task]]] = [
        (
            instance.node,
            [],
        )
        for instance in associated_instances
        if instance.node.Spec
        and (instance.node.Spec.Availability == Availability.drain)
    ]

    for task in pending_tasks:
        if try_assigning_task_to_node(task, activatable_nodes):
            continue

    nodes_to_activate = [
        (node, assigned_tasks)
        for node, assigned_tasks in activatable_nodes
        if assigned_tasks
    ]

    async def _activate_and_notify(node: Node, tasks: list[Task]) -> list[Task]:
        await asyncio.gather(
            *(
                utils_docker.set_node_availability(docker_client, node, available=True),
                log_tasks_message(
                    app,
                    tasks,
                    "cluster adjusted, service should start shortly...",
                ),
                progress_tasks_message(app, tasks, progress=1.0),
            )
        )
        return tasks

    # scale up
    list_treated_tasks = await asyncio.gather(
        *(_activate_and_notify(node, tasks) for node, tasks in nodes_to_activate)
    )

    return list(itertools.chain(*list_treated_tasks))


async def _find_needed_instances(
    app: FastAPI,
    pending_tasks: list[Task],
    available_ec2_types: list[EC2Instance],
    attached_ec2_instances: list[AssociatedInstance],
    pending_ec2_instances: list[EC2InstanceData],
) -> dict[EC2Instance, int]:
    type_to_instance_map = {t.name: t for t in available_ec2_types}

    list_of_existing_instance_to_tasks: list[tuple[EC2InstanceData, list[Task]]] = [
        (i, []) for i in pending_ec2_instances
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

    num_instances_per_type_from_tasks = dict(
        collections.Counter(t for t, _ in list_of_new_instance_to_tasks)
    )
    app_settings: ApplicationSettings = app.state.settings
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    num_instances_per_type_from_tasks = {
        i_type: num_i
        + app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER
        for i_type, num_i in num_instances_per_type_from_tasks.items()
        if num_i > 0
    }

    return num_instances_per_type_from_tasks


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
    attached_instances: list[AssociatedInstance],
    pending_instances: list[EC2InstanceData],
    pending_tasks: list[Task],
) -> list[EC2InstanceData]:
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
        attached_instances,
        pending_instances,
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
        pending_instances.extend(new_pending_instances)
        await progress_tasks_message(app, pending_tasks, 0)
    return pending_instances


async def _try_attach_pending_ec2s(
    app: FastAPI,
    attached_ec2s: list[AssociatedInstance],
    pending_ec2s: list[EC2InstanceData],
) -> tuple[list[AssociatedInstance], list[EC2InstanceData]]:
    """label the instances that connected to the swarm that are missing the monitoring labels"""
    newly_attached_nodes: list[AssociatedInstance] = []
    still_pending_ec2: list[EC2InstanceData] = []
    app_settings: ApplicationSettings = app.state.settings
    for instance_data in pending_ec2s:
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
    attached_ec2s.extend(newly_attached_nodes)
    return (attached_ec2s, still_pending_ec2)


async def cluster_scaling_from_labelled_services(app: FastAPI) -> None:
    """Check that there are no pending tasks requiring additional resources in the cluster (docker swarm)
    If there are such tasks, this method will allocate new machines in AWS to cope with
    the additional load.
    """
    app_settings: ApplicationSettings = app.state.settings
    assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec
    docker_client = get_docker_client(app)

    # 1. get monitored nodes information and resources
    monitored_nodes = await utils_docker.get_monitored_nodes(
        docker_client,
        node_labels=app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS,
    )

    # 2. Cleanup nodes that are gone or were terminated
    monitored_nodes = [
        n
        for n in monitored_nodes
        if n not in await utils_docker.remove_nodes(docker_client, monitored_nodes)
    ]

    # 3. find node-ec2_instances associations
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    running_ec2_instances = await get_ec2_client(app).get_instances(
        app_settings.AUTOSCALING_EC2_INSTANCES,
        list(ec2.get_ec2_tags(app_settings).keys()),
    )
    attached_ec2s, pending_ec2s = await associate_ec2_instances_with_nodes(
        monitored_nodes, running_ec2_instances
    )

    logger.info("current ec2s: %s, %s", f"{attached_ec2s=}", f"{pending_ec2s=}")

    # 3. Attach/Label new connected instances
    attached_ec2s, pending_ec2s = await _try_attach_pending_ec2s(
        app, attached_ec2s, pending_ec2s
    )

    # 4. Scale up the cluster if there are pending tasks, else see if we shall scale down
    if pending_tasks := await utils_docker.pending_service_tasks_with_insufficient_resources(
        docker_client,
        service_labels=app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_SERVICE_LABELS,
    ):
        # we have a number of pending tasks, try to resolve them with drained nodes if possible
        assigned_tasks = [
            t.ID
            for t in await _activate_drained_nodes(app, attached_ec2s, pending_tasks)
        ]
        # let's check if there are still pending tasks
        if pending_tasks := [t for t in pending_tasks if t.ID not in assigned_tasks]:
            # yes? then scale up
            pending_ec2s = await _scale_up_cluster(
                app, attached_ec2s, pending_ec2s, pending_tasks
            )
    else:
        await _deactivate_empty_nodes(app, attached_ec2s)
        await _try_scale_down_cluster(app, attached_ec2s)
        # await _ensure_buffer_machine_runs(app, monitored_nodes)

    # 4. Notify anyone interested of current state
    await post_autoscaling_status_message(app, attached_ec2s, pending_ec2s)
