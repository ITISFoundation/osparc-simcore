import asyncio
import collections
import itertools
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import cast

from fastapi import FastAPI
from models_library.docker import DockerLabelKey
from models_library.generated_models.docker_rest_api import Availability, Node, Task
from pydantic import parse_obj_as
from types_aiobotocore_ec2.literals import InstanceTypeType

from .core.errors import (
    Ec2InstanceNotFoundError,
    Ec2InvalidDnsNameError,
    Ec2TooManyInstancesError,
)
from .core.settings import ApplicationSettings
from .models import EC2Instance, Resources
from .modules.docker import get_docker_client
from .modules.ec2 import EC2InstanceData, get_ec2_client
from .utils import ec2, rabbitmq, utils_docker
from .utils.rabbitmq import post_autoscaling_status_message

logger = logging.getLogger(__name__)

_EC2_INTERNAL_DNS_RE: re.Pattern = re.compile(r"^(?P<ip>ip-[0-9-]+).+$")


async def _mark_empty_active_nodes_to_drain(
    app: FastAPI,
    monitored_nodes: list[Node],
) -> None:
    app_settings: ApplicationSettings = app.state.settings
    assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec
    docker_client = get_docker_client(app)
    active_empty_nodes = [
        node
        for node in monitored_nodes
        if (
            await utils_docker.compute_node_used_resources(
                docker_client,
                node,
                service_labels=app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_SERVICE_LABELS,
            )
            == Resources.create_as_empty()
        )
        and (node.Spec is not None)
        and (node.Spec.Availability == Availability.active)
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


async def _find_terminateable_nodes(
    app: FastAPI, monitored_nodes: list[Node]
) -> list[tuple[Node, EC2InstanceData]]:
    app_settings: ApplicationSettings = app.state.settings
    assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec
    docker_client = get_docker_client(app)

    # NOTE: we want the drained nodes where no monitored service is running anymore
    drained_empty_nodes = [
        node
        for node in monitored_nodes
        if (
            await utils_docker.compute_node_used_resources(
                docker_client,
                node,
                service_labels=app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_SERVICE_LABELS,
            )
            == Resources.create_as_empty()
        )
        and (node.Spec is not None)
        and (node.Spec.Availability == Availability.drain)
    ]
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec

    # we keep a buffer of nodes always on the ready
    drained_empty_nodes = drained_empty_nodes[
        app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER :
    ]

    if not drained_empty_nodes:
        # there is nothing to terminate here
        return []

    # get the corresponding ec2 instance data
    # NOTE: some might be in the process of terminating and will not be found
    ec2_client = get_ec2_client(app)
    drained_empty_ec2_instances = await asyncio.gather(
        *(
            ec2_client.get_running_instance(
                app_settings.AUTOSCALING_EC2_INSTANCES,
                tag_keys=[
                    "io.simcore.autoscaling.version",
                ],
                instance_host_name=node.Description.Hostname,
            )
            for node in drained_empty_nodes
            if node.Description and node.Description.Hostname
        ),
        return_exceptions=True,
    )

    terminateable_nodes: list[tuple[Node, EC2InstanceData]] = []

    for node, ec2_instance_data in zip(
        drained_empty_nodes, drained_empty_ec2_instances
    ):
        if isinstance(ec2_instance_data, Ec2InstanceNotFoundError):
            # skip if already terminating
            continue
        # NOTE: AWS price is hourly based (e.g. same price for a machine used 2 minutes or 1 hour, so we wait until 55 minutes)
        elapsed_time_since_launched = (
            datetime.utcnow().replace(tzinfo=timezone.utc)
            - ec2_instance_data.launch_time
        )
        elapsed_time_since_full_hour = elapsed_time_since_launched % timedelta(hours=1)
        if (
            elapsed_time_since_full_hour
            >= app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
        ):
            # let's terminate that one
            terminateable_nodes.append((node, ec2_instance_data))

    if terminateable_nodes:
        logger.info(
            "the following nodes were found to be terminateable: '%s'",
            f"{[node.Description.Hostname for node,_ in terminateable_nodes if node.Description]}",
        )
    return terminateable_nodes


async def _try_scale_down_cluster(app: FastAPI, monitored_nodes: list[Node]) -> None:
    # 2. once it is in draining mode and we are nearing a modulo of an hour we can start the termination procedure
    # NOTE: the nodes that were just changed to drain above will be eventually terminated on the next iteration
    if terminateable_nodes := await _find_terminateable_nodes(app, monitored_nodes):
        await asyncio.gather(
            *(
                get_ec2_client(app).terminate_instance(ec2_instance_data)
                for _, ec2_instance_data in terminateable_nodes
            )
        )
        logger.info(
            "terminated the following machines: '%s'",
            f"{[node.Description.Hostname for node,_ in terminateable_nodes if node.Description]}",
        )
        # since these nodes are being terminated, remove them from the swarm
        await utils_docker.remove_nodes(
            get_docker_client(app),
            [node for node, _ in terminateable_nodes],
            force=True,
        )

    # 3. we could ask on rabbit whether someone would like to keep that machine for something (like the agent for example), if that is the case, we wait another hour and ask again?
    # 4.


def _try_assigning_task_to_node(
    pending_task: Task, node_to_tasks: list[tuple[Node, list[Task]]]
) -> bool:
    for node, node_assigned_tasks in node_to_tasks:
        instance_total_resource = utils_docker.get_node_total_resources(node)
        tasks_needed_resources = utils_docker.compute_tasks_needed_resources(
            node_assigned_tasks
        )
        if (
            instance_total_resource - tasks_needed_resources
        ) >= utils_docker.get_max_resources_from_docker_task(pending_task):
            node_assigned_tasks.append(pending_task)
            return True
    return False


async def _try_scale_up_with_drained_nodes(
    app: FastAPI,
    monitored_nodes: list[Node],
    pending_tasks: list[Task],
) -> list[Task]:
    """returns the tasks that were assigned to the drained nodes"""
    docker_client = get_docker_client(app)
    if not pending_tasks:
        return []
    activatable_nodes: list[tuple[Node, list[Task]]] = [
        (
            node,
            [],
        )
        for node in monitored_nodes
        if node.Spec and (node.Spec.Availability == Availability.drain)
    ]

    for task in pending_tasks:
        if _try_assigning_task_to_node(task, activatable_nodes):
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
                _log_tasks_message(
                    app,
                    tasks,
                    "cluster adjusted, service should start shortly...",
                ),
                _progress_tasks_message(app, tasks, progress=1.0),
            )
        )
        return tasks

    # scale up
    list_treated_tasks = await asyncio.gather(
        *(_activate_and_notify(node, tasks) for node, tasks in nodes_to_activate)
    )

    return list(itertools.chain(*list_treated_tasks))


async def _try_assigning_task_to_pending_instances(
    app: FastAPI,
    pending_task: Task,
    list_of_pending_instance_to_tasks: list[tuple[EC2InstanceData, list[Task]]],
    type_to_instance_map: dict[str, EC2Instance],
) -> bool:
    for instance, instance_assigned_tasks in list_of_pending_instance_to_tasks:
        instance_type = type_to_instance_map[instance.type]
        instance_total_resources = Resources(
            cpus=instance_type.cpus, ram=instance_type.ram
        )
        tasks_needed_resources = utils_docker.compute_tasks_needed_resources(
            instance_assigned_tasks
        )
        if (
            instance_total_resources - tasks_needed_resources
        ) >= utils_docker.get_max_resources_from_docker_task(pending_task):
            instance_assigned_tasks.append(pending_task)
            await _log_tasks_message(
                app,
                [pending_task],
                "scaling up of cluster in progress...awaiting new machines...please wait...",
            )
            await _progress_tasks_message(
                app,
                [pending_task],
                (datetime.utcnow() - instance.launch_time).total_seconds(),
            )
            return True
    return False


def _try_assigning_task_to_instances(
    pending_task: Task, list_of_instance_to_tasks: list[tuple[EC2Instance, list[Task]]]
) -> bool:
    for instance, instance_assigned_tasks in list_of_instance_to_tasks:
        instance_total_resource = Resources(cpus=instance.cpus, ram=instance.ram)
        tasks_needed_resources = utils_docker.compute_tasks_needed_resources(
            instance_assigned_tasks
        )
        if (
            instance_total_resource - tasks_needed_resources
        ) >= utils_docker.get_max_resources_from_docker_task(pending_task):
            instance_assigned_tasks.append(pending_task)
            return True
    return False


async def _find_needed_instances(
    app: FastAPI,
    pending_tasks: list[Task],
    available_ec2_types: list[EC2Instance],
    pending_ec2_instances: list[EC2InstanceData],
) -> dict[EC2Instance, int]:
    existing_instance_types = await get_ec2_client(app).get_ec2_instance_capabilities(
        {i.type for i in pending_ec2_instances}
    )
    type_to_instance_map = {t.name: t for t in existing_instance_types}

    list_of_existing_instance_to_tasks: list[tuple[EC2InstanceData, list[Task]]] = [
        (i, []) for i in pending_ec2_instances
    ]
    list_of_new_instance_to_tasks: list[tuple[EC2Instance, list[Task]]] = []
    for task in pending_tasks:
        if await _try_assigning_task_to_pending_instances(
            app, task, list_of_existing_instance_to_tasks, type_to_instance_map
        ):
            continue

        if _try_assigning_task_to_instances(task, list_of_new_instance_to_tasks):
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

    num_instances_per_type = dict(
        collections.Counter(t for t, _ in list_of_new_instance_to_tasks)
    )
    return num_instances_per_type


def _get_docker_node_name_from_aws_private_dns_name(
    ec2_instance_data: EC2InstanceData,
) -> str:
    if match := re.match(_EC2_INTERNAL_DNS_RE, ec2_instance_data.aws_private_dns):
        return match.group(1)
    raise Ec2InvalidDnsNameError(aws_private_dns_name=ec2_instance_data.aws_private_dns)


async def _start_instances(
    app: FastAPI, needed_instances: dict[EC2Instance, int], tasks: list[Task]
) -> None:
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
                tags=ec2.get_ec2_tags(app_settings.AUTOSCALING_NODES_MONITORING),
                startup_script=startup_script,
                number_of_instances=instance_num,
            )
            for instance, instance_num in needed_instances.items()
        ),
        return_exceptions=True,
    )
    # parse results
    last_issue = ""
    for r in results:
        if isinstance(r, Ec2TooManyInstancesError):
            await _log_tasks_message(
                app,
                tasks,
                "Exceptionally high load on computational cluster, please try again later.",
                level=logging.ERROR,
            )
        if isinstance(r, Exception):
            logger.error("Unexpected error happened when starting EC2 instance: %s", r)
            last_issue = f"{r}"

    log_message = f"{sum(n for n in needed_instances.values())} new machines launched, it might take up to 3 minutes to start, Please wait..."
    if last_issue:
        log_message += "\nUnexpected issues detected, probably due to high load, please contact support"
    await _log_tasks_message(
        app,
        tasks,
        log_message,
    )


def _get_docker_tags(app_settings: ApplicationSettings) -> dict[DockerLabelKey, str]:
    assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec
    return {
        tag_key: "true"
        for tag_key in app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS
    } | {
        tag_key: "true"
        for tag_key in app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NEW_NODES_LABELS
    }


async def _log_tasks_message(
    app: FastAPI, tasks: list[Task], message: str, *, level: int = logging.INFO
) -> None:
    await asyncio.gather(
        *(rabbitmq.post_task_log_message(app, task, message, level) for task in tasks),
        return_exceptions=True,
    )


async def _progress_tasks_message(
    app: FastAPI, tasks: list[Task], progress: float
) -> None:
    await asyncio.gather(
        *(rabbitmq.post_task_progress_message(app, task, progress) for task in tasks),
        return_exceptions=True,
    )


async def _ensure_buffer_machine_runs(
    app: FastAPI, monitored_nodes: list[Node]
) -> None:
    app_settings: ApplicationSettings = app.state.settings
    assert app_settings.AUTOSCALING_EC2_ACCESS  # nosec
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec
    docker_client = get_docker_client(app)
    drained_empty_nodes = [
        node
        for node in monitored_nodes
        if (
            await utils_docker.compute_node_used_resources(
                docker_client,
                node,
                service_labels=app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_SERVICE_LABELS,
            )
            == Resources.create_as_empty()
        )
        and (node.Spec is not None)
        and (node.Spec.Availability == Availability.drain)
    ]
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec

    # we keep a buffer of nodes always on the ready
    if (
        len(drained_empty_nodes)
        < app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER
    ):
        allowed_instance_types = await get_ec2_client(
            app
        ).get_ec2_instance_capabilities(
            cast(  # type: ignore
                list[InstanceTypeType],
                app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES,
            )
        )

        missing_buffer_instances = (
            app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER
            - len(drained_empty_nodes)
        )
        # NOTE: we start the first instance type available in the list
        for (
            instance_type
        ) in app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES:
            if filtered_instance_types := list(
                filter(
                    lambda x: x.name == instance_type,
                    allowed_instance_types,
                )
            ):
                await _start_instances(
                    app,
                    {
                        filtered_instance_types[0]: missing_buffer_instances,
                    },
                    [],
                )
                return


async def _scale_up_cluster(
    app: FastAPI, monitored_nodes: list[Node], pending_tasks: list[Task]
) -> None:
    app_settings: ApplicationSettings = app.state.settings
    assert app_settings.AUTOSCALING_EC2_ACCESS  # nosec
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec
    ec2_client = get_ec2_client(app)

    # check if scaling up is not already ongoing
    existing_ec2_instances: list[EC2InstanceData] = await ec2_client.get_instances(
        app_settings.AUTOSCALING_EC2_INSTANCES,
        tag_keys=list(
            ec2.get_ec2_tags(app_settings.AUTOSCALING_NODES_MONITORING).keys()
        ),
    )
    # find the currently starting instances (aka not connected to docker swarm yet)
    pending_ec2_instances: list[EC2InstanceData] = []
    all_monitored_node_names = [
        n.Description.Hostname for n in monitored_nodes if n.Description
    ]
    for instance_data in existing_ec2_instances:
        try:
            docker_node_name = _get_docker_node_name_from_aws_private_dns_name(
                instance_data
            )
        except Ec2InvalidDnsNameError:
            logger.exception("Unexcepted EC2 private dns name")
            continue
        if docker_node_name in all_monitored_node_names:
            continue
        pending_ec2_instances.append(instance_data)

    allowed_instance_types = await ec2_client.get_ec2_instance_capabilities(
        cast(  # type: ignore
            set[InstanceTypeType],
            set(
                app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES,
            ),
        )
    )
    # some instances might be able to run several tasks
    needed_ec2_instances = await _find_needed_instances(
        app, pending_tasks, allowed_instance_types, pending_ec2_instances
    )

    # let's start these
    if needed_ec2_instances:
        await _log_tasks_message(
            app,
            pending_tasks,
            "service is pending due to missing resources, scaling up cluster now\n"
            f"{sum(n for n in needed_ec2_instances.values())} new machines will be added, please wait...",
        )
        await _start_instances(app, needed_ec2_instances, pending_tasks)
        await _progress_tasks_message(app, pending_tasks, 0)


async def _attach_new_ec2_instances(
    app: FastAPI, monitored_nodes: list[Node]
) -> list[Node]:
    """label the instances that connected to the swarm that are missing the monitoring labels"""
    app_settings: ApplicationSettings = app.state.settings
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec
    running_ec2_instances = await get_ec2_client(app).get_instances(
        app_settings.AUTOSCALING_EC2_INSTANCES,
        list(ec2.get_ec2_tags(app_settings.AUTOSCALING_NODES_MONITORING).keys()),
        state_names=["running"],
    )
    # check that all running instances are already labelled correctly
    newly_attached_nodes = []
    all_monitored_node_names = [
        n.Description.Hostname for n in monitored_nodes if n.Description
    ]
    for instance_data in running_ec2_instances:
        try:
            docker_node_name = _get_docker_node_name_from_aws_private_dns_name(
                instance_data
            )
        except Ec2InvalidDnsNameError:
            logger.exception("Unexcepted EC2 private dns name")
            continue

        # already monitored then we skip
        if docker_node_name in all_monitored_node_names:
            continue
        # this one is missing, let's check if it attached already
        if new_node := await utils_docker.try_get_node_with_name(
            get_docker_client(app), docker_node_name
        ):
            # it is attached, let's label it, but keep it as drained
            new_node = await utils_docker.tag_node(
                get_docker_client(app),
                new_node,
                tags=_get_docker_tags(app_settings),
                available=False,
            )
            newly_attached_nodes.append(new_node)
    return newly_attached_nodes


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
    removed_nodes = await utils_docker.remove_nodes(docker_client, monitored_nodes)
    monitored_nodes = [n for n in monitored_nodes if n not in removed_nodes]

    # 3. Label new connected instances
    new_nodes = await _attach_new_ec2_instances(app, monitored_nodes)
    monitored_nodes.extend(new_nodes)

    # 4. Scale up the cluster if there are pending tasks, else see if we shall scale down
    if pending_tasks := await utils_docker.pending_service_tasks_with_insufficient_resources(
        docker_client,
        service_labels=app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_SERVICE_LABELS,
    ):
        # we have a number of pending tasks, try to resolve them with drained nodes if possible
        treated_tasks = await _try_scale_up_with_drained_nodes(
            app, monitored_nodes, pending_tasks
        )
        treated_task_ids = [t.ID for t in treated_tasks]
        # clean the pending tasks with the ones that were treated
        pending_tasks = [t for t in pending_tasks if t.ID not in treated_task_ids]

        # let's check if there are still pending tasks
        if pending_tasks:
            # yes? then scale up
            await _scale_up_cluster(app, monitored_nodes, pending_tasks)
    else:
        await _mark_empty_active_nodes_to_drain(app, monitored_nodes)
        await _try_scale_down_cluster(app, monitored_nodes)
        await _ensure_buffer_machine_runs(app, monitored_nodes)

    # 4. Notify anyone interested of current state
    await post_autoscaling_status_message(app, monitored_nodes)
