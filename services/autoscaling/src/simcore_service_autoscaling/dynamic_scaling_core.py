import logging
from datetime import datetime

from fastapi import FastAPI

from . import utils_aws, utils_docker
from .core.settings import ApplicationSettings

logger = logging.getLogger(__name__)


async def check_dynamic_resources(app: FastAPI) -> None:
    app_settings: ApplicationSettings = app.state.settings
    if not await utils_docker.pending_service_tasks_with_insufficient_resources():
        logger.debug("the swarm has enough computing resources at the moment")
        return

    cluster_total_resources = await utils_docker.compute_cluster_total_resources(
        app_settings.AUTOSCALING_MONITORED_NODES_LABELS
    )
    logger.debug("%s", f"{cluster_total_resources=}")
    cluster_used_resources = await utils_docker.compute_cluster_used_resources(
        cluster_total_resources.node_ids
    )
    logger.debug("%s", f"{cluster_used_resources=}")

    ec2_instance_needed = utils_aws.find_needed_ec2_instance(4, 4)
    logger.debug("%s", f"{ec2_instance_needed=}")

    await utils_aws.start_instance_aws(
        app_settings.AUTOSCALING_AWS,
        instance_type=ec2_instance_needed.name,
        tags=["autoscaling created node", f"created at {datetime.utcnow()}"],
    )
