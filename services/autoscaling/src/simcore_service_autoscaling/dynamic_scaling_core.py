import asyncio
import json
import logging
import re
from datetime import datetime, timedelta

from fastapi import FastAPI
from models_library.generated_models.docker_rest_api import Availability, Node, Task
from pydantic import parse_obj_as
from types_aiobotocore_ec2.literals import InstanceTypeType

from ._meta import VERSION
from .core.errors import Ec2InstanceNotFoundError
from .core.settings import ApplicationSettings
from .models import Resources
from .modules.docker import get_docker_client
from .modules.ec2 import EC2InstanceData, get_ec2_client
from .utils import ec2, rabbitmq, utils_docker

logger = logging.getLogger(__name__)

_EC2_INTERNAL_DNS_RE: re.Pattern = re.compile(r"^(?P<ip>ip-[0-9-]+).+$")


async def _scale_down_cluster(app: FastAPI, monitored_nodes: list[Node]) -> None:
    # NOTE: when do we scale down???
    app_settings: ApplicationSettings = app.state.settings

    # 1. if a machine has nothing running on it, it should at least be set to drain as a first step (we could undrain it if there is a sudden need)
    docker_client = get_docker_client(app)
    active_empty_nodes = [
        node
        for node in monitored_nodes
        if (
            await utils_docker.compute_node_used_resources(docker_client, node)
            == Resources.empty_resources()
        )
        and (node.Spec is not None)
        and (node.Spec.Availability == Availability.active)
    ]
    await asyncio.gather(
        *(
            utils_docker.tag_node(docker_client, node, tags={}, available=False)
            for node in active_empty_nodes
        )
    )

    # 2. once it is in draining mode and we are nearing a modulo of an hour we can start the termination procedure (parametrize this)
    # NOTE: the nodes that were just changed to drain above will be eventually terminated on the next iteration
    drained_empty_nodes = [
        node
        for node in monitored_nodes
        if (
            await utils_docker.compute_node_used_resources(docker_client, node)
            == Resources.empty_resources()
        )
        and (node.Spec is not None)
        and (node.Spec.Availability == Availability.drain)
    ]
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec

    terminateable_nodes: list[tuple[Node, EC2InstanceData]] = []
    for node in drained_empty_nodes:
        assert node.Description  # nosec
        assert node.Description.Hostname  # nosec
        ec2_instance_data = await get_ec2_client(app).get_running_instance(
            app_settings.AUTOSCALING_EC2_INSTANCES,
            ["io.simcore.autoscaling.created", "io.simcore.autoscaling.version"],
            node.Description.Hostname,
        )
        time_since_instance_was_launched = (
            datetime.utcnow() - ec2_instance_data.launch_time
        )
        minutes_since_full_hour = time_since_instance_was_launched % timedelta(hours=1)
        if minutes_since_full_hour > timedelta(minutes=55):
            # let's terminate that one
            terminateable_nodes.append((node, ec2_instance_data))

    if terminateable_nodes:
        await asyncio.gather(
            *(
                get_ec2_client(app).terminate_instance(ec2_instance_data)
                for _, ec2_instance_data in terminateable_nodes
            )
        )

    # 3. we could ask on rabbit whether someone would like to keep that machine for something (like the agent for example), if that is the case, we wait another hour and ask again?
    # 4.


async def _scale_up_cluster(app: FastAPI, pending_tasks: list[Task]) -> None:
    app_settings: ApplicationSettings = app.state.settings
    assert app_settings.AUTOSCALING_EC2_ACCESS  # nosec
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    ec2_client = get_ec2_client(app)
    list_of_ec2_instances = await ec2_client.get_ec2_instance_capabilities(
        app_settings.AUTOSCALING_EC2_INSTANCES
    )
    for task in pending_tasks:
        await rabbitmq.post_log_message(
            app,
            task,
            "service is pending due to insufficient resources, scaling up cluster please wait...",
            logging.INFO,
        )
        try:
            ec2_instances_needed = [
                ec2.find_best_fitting_ec2_instance(
                    list_of_ec2_instances,
                    utils_docker.get_max_resources_from_docker_task(task),
                    score_type=ec2.closest_instance_policy,
                )
            ]
            assert app_settings.AUTOSCALING_EC2_ACCESS  # nosec
            assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec

            logger.debug("%s", f"{ec2_instances_needed[0]=}")
            new_instance_dns_name = await ec2_client.start_aws_instance(
                app_settings.AUTOSCALING_EC2_INSTANCES,
                instance_type=parse_obj_as(
                    InstanceTypeType, ec2_instances_needed[0].name
                ),
                tags={
                    "io.simcore.autoscaling.created": f"{datetime.utcnow()}",
                    "io.simcore.autoscaling.version": f"{VERSION}",
                    "io.simcore.autoscaling.monitored_nodes_labels": json.dumps(
                        app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS
                    ),
                    "io.simcore.autoscaling.monitored_services_labels": json.dumps(
                        app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_SERVICE_LABELS
                    ),
                },
                startup_script=await utils_docker.get_docker_swarm_join_bash_command(),
            )

            # NOTE: new_instance_dns_name is of type ip-123-23-23-3.ec2.internal and we need only the first part
            if match := re.match(_EC2_INTERNAL_DNS_RE, new_instance_dns_name):
                new_instance_dns_name = match.group(1)
                new_node = await utils_docker.wait_for_node(
                    get_docker_client(app), new_instance_dns_name
                )
                await utils_docker.tag_node(
                    get_docker_client(app),
                    new_node,
                    tags={
                        tag_key: "true"
                        for tag_key in app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS
                    }
                    | {
                        tag_key: "true"
                        for tag_key in app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NEW_NODES_LABELS
                    },
                    available=True,
                )
                await rabbitmq.post_log_message(
                    app,
                    task,
                    "cluster was scaled up and is now ready to run service",
                    logging.INFO,
                )
            # NOTE: in this first trial we start one instance at a time
            # In the next iteration, some tasks might already run with that instance
            break
        except Ec2InstanceNotFoundError:
            logger.error(
                "Task %s needs more resources than any EC2 instance "
                "can provide with the current configuration. Please check.",
                {
                    f"{task.Name if task.Name else 'unknown task name'}:{task.ServiceID if task.ServiceID else 'unknown service ID'}"
                },
            )


async def check_dynamic_resources(app: FastAPI) -> None:
    """Check that there are no pending tasks requiring additional resources in the cluster (docker swarm)
    If there are such tasks, this method will allocate new machines in AWS to cope with
    the additional load.
    """
    app_settings: ApplicationSettings = app.state.settings
    assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec

    # 1. get monitored nodes information and resources
    docker_client = get_docker_client(app)
    monitored_nodes = await utils_docker.get_monitored_nodes(
        docker_client,
        node_labels=app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS,
    )

    cluster_total_resources = await utils_docker.compute_cluster_total_resources(
        monitored_nodes
    )
    logger.info("%s", f"{cluster_total_resources=}")
    cluster_used_resources = await utils_docker.compute_cluster_used_resources(
        docker_client, monitored_nodes
    )
    logger.info("%s", f"{cluster_used_resources=}")

    # 2. Remove nodes that are gone
    await utils_docker.remove_monitored_down_nodes(docker_client, monitored_nodes)

    # 3. Scale up nodes if there are pending tasks
    pending_tasks = await utils_docker.pending_service_tasks_with_insufficient_resources(
        docker_client,
        service_labels=app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_SERVICE_LABELS,
    )
    await rabbitmq.post_state_message(
        app,
        monitored_nodes,
        cluster_total_resources,
        cluster_used_resources,
        pending_tasks,
    )

    if not pending_tasks:
        logger.debug("no pending tasks with insufficient resources at the moment")
        await _scale_down_cluster(app, monitored_nodes)
    else:
        await _scale_up_cluster(app, pending_tasks)
