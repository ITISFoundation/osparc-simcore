import json
import logging
import re
from datetime import datetime

from fastapi import FastAPI
from models_library.generated_models.docker_rest_api import Task
from pydantic import parse_obj_as
from types_aiobotocore_ec2.literals import InstanceTypeType

from ._meta import VERSION
from .core.errors import Ec2InstanceNotFoundError
from .core.settings import ApplicationSettings
from .modules.docker import get_docker_client
from .modules.ec2 import get_ec2_client
from .utils import ec2, rabbitmq, utils_docker

logger = logging.getLogger(__name__)

_EC2_INTERNAL_DNS_RE: re.Pattern = re.compile(r"^(?P<ip>ip-[0-9-]+).+$")


async def _scale_down_cluster(app: FastAPI) -> None:
    ...


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
        await _scale_down_cluster(app)
        return

    await _scale_up_cluster(app, pending_tasks)
