import json
import logging
from datetime import datetime

from fastapi import FastAPI
from mypy_boto3_ec2.literals import InstanceTypeType
from pydantic import parse_obj_as

from . import utils_aws, utils_docker
from ._meta import VERSION
from .core.errors import Ec2InstanceNotFoundError
from .core.settings import ApplicationSettings

logger = logging.getLogger(__name__)


async def check_dynamic_resources(app: FastAPI) -> None:
    """Check that there are no pending tasks requiring additional resources in the cluster (docker swarm)
    If there are such tasks, this method will allocate new machines in AWS to cope with
    the additional load.
    """
    app_settings: ApplicationSettings = app.state.settings
    assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec
    pending_tasks = await utils_docker.pending_service_tasks_with_insufficient_resources(
        service_labels=app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_SERVICE_LABELS
    )
    if not pending_tasks:
        logger.debug("no pending tasks with insufficient resources at the moment")
        return

    logger.info(
        "%s service task(s) with %s label(s) are pending due to insufficient resources",
        f"{len(pending_tasks)}",
        f"{app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_SERVICE_LABELS}",
    )

    monitored_nodes = await utils_docker.get_monitored_nodes(
        node_labels=app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS
    )

    cluster_total_resources = await utils_docker.compute_cluster_total_resources(
        monitored_nodes
    )
    logger.info("current %s", f"{cluster_total_resources=}")
    cluster_used_resources = await utils_docker.compute_cluster_used_resources(
        monitored_nodes
    )
    logger.info("current %s", f"{cluster_used_resources=}")

    assert app_settings.AUTOSCALING_EC2_ACCESS  # nosec
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    list_of_ec2_instances = utils_aws.get_ec2_instance_capabilities(
        app_settings.AUTOSCALING_EC2_ACCESS, app_settings.AUTOSCALING_EC2_INSTANCES
    )

    for task in pending_tasks:
        try:
            ec2_instances_needed = [
                utils_aws.find_best_fitting_ec2_instance(
                    list_of_ec2_instances,
                    utils_docker.get_resources_from_docker_task(task),
                    score_type=utils_aws.closest_instance_policy,
                )
            ]
            assert app_settings.AUTOSCALING_EC2_ACCESS  # nosec
            assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec

            logger.debug("%s", f"{ec2_instances_needed[0]=}")
            new_instance_dns_name = utils_aws.start_aws_instance(
                app_settings.AUTOSCALING_EC2_ACCESS,
                app_settings.AUTOSCALING_EC2_INSTANCES,
                instance_type=parse_obj_as(
                    InstanceTypeType, ec2_instances_needed[0].name
                ),
                tags={
                    "io.osparc.autoscaling.created": f"{datetime.utcnow()}",
                    "io.osparc.autoscaling.version": f"{VERSION}",
                    "io.osparc.autoscaling.monitored_nodes_labels": json.dumps(
                        app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS
                    ),
                    "io.osparc.autoscaling.monitored_services_labels": json.dumps(
                        app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_SERVICE_LABELS
                    ),
                },
                startup_script=await utils_docker.get_docker_swarm_join_bash_command(),
            )

            new_node = await utils_docker.wait_for_node(new_instance_dns_name)
            await utils_docker.tag_node(
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
            # NOTE: in this first trial we start one instance at a time
            # In the next iteration, some tasks might already run with that instance
            break
        except Ec2InstanceNotFoundError:
            logger.error(
                "Task %s needs more resources than any EC2 instance "
                "can provide with the current configuration. Please check.",
                {f"{task.Name=}:{task.ServiceID=}"},
            )
