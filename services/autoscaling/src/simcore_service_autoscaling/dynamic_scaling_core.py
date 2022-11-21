import logging
from datetime import datetime

from fastapi import FastAPI

from . import utils_aws, utils_docker
from .core.errors import Ec2InstanceNotFoundError
from .core.settings import ApplicationSettings

logger = logging.getLogger(__name__)


async def check_dynamic_resources(app: FastAPI) -> None:
    """Check that there are no pending tasks requiring additional resources in the cluster (docker swarm)
    If there are such tasks, this method will allocate new machines in AWS to cope with
    the additional load.
    """
    app_settings: ApplicationSettings = app.state.settings
    pending_tasks = (
        await utils_docker.pending_service_tasks_with_insufficient_resources(
            service_labels=app_settings.AUTOSCALING_MONITORED_SERVICES_LABELS
        )
    )
    if not pending_tasks:
        logger.debug("no pending tasks with insufficient resources at the moment")
        return

    logger.info(
        "%s service task(s) with %s label(s) are pending due to insufficient resources",
        f"{len(pending_tasks)}",
        f"{app_settings.AUTOSCALING_MONITORED_SERVICES_LABELS}",
    )

    monitored_nodes = await utils_docker.get_monitored_nodes(
        node_labels=app_settings.AUTOSCALING_MONITORED_NODES_LABELS
    )

    cluster_total_resources = await utils_docker.compute_cluster_total_resources(
        monitored_nodes
    )
    logger.info("current %s", f"{cluster_total_resources=}")
    cluster_used_resources = await utils_docker.compute_cluster_used_resources(
        monitored_nodes
    )
    logger.info("current %s", f"{cluster_used_resources=}")

    assert app_settings.AUTOSCALING_AWS  # nosec
    list_of_ec2_instances = utils_aws.get_ec2_instance_capabilities(
        app_settings.AUTOSCALING_AWS
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
            assert app_settings.AUTOSCALING_AWS  # nosec

            logger.debug("%s", f"{ec2_instances_needed[0]=}")
            utils_aws.start_instance_aws(
                app_settings.AUTOSCALING_AWS,
                instance_type=ec2_instances_needed[0].name,
                tags=["autoscaling created node", f"created at {datetime.utcnow()}"],
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
