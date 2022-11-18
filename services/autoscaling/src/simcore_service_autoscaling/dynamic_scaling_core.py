import logging

from fastapi import FastAPI
from pydantic import ByteSize, parse_obj_as

from . import models, utils_aws, utils_docker
from .core.settings import ApplicationSettings

logger = logging.getLogger(__name__)


async def check_dynamic_resources(app: FastAPI) -> None:
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

    ec2_instance_needed = utils_aws.find_best_fitting_ec2_instance(
        list_of_ec2_instances,
        models.Resources(cpus=4, ram=parse_obj_as(ByteSize, "2Gib")),
    )
    logger.debug("%s", f"{ec2_instance_needed=}")

    assert app_settings.AUTOSCALING_AWS  # nosec
    # await utils_aws.start_instance_aws(
    #     app_settings.AUTOSCALING_AWS,
    #     instance_type=ec2_instance_needed.name,
    #     tags=["autoscaling created node", f"created at {datetime.utcnow()}"],
    # )
