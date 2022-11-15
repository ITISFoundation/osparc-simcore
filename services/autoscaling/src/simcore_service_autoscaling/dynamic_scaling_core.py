import logging

from fastapi import FastAPI

from . import utils_aws, utils_docker
from .core.settings import ApplicationSettings

logger = logging.getLogger(__name__)


async def check_dynamic_resources(app: FastAPI) -> None:
    app_settings: ApplicationSettings = app.state.settings
    if not await utils_docker.pending_services_with_insufficient_resources():
        logger.debug("the swarm has enough computing resources at the moment")
        return

    current_cluster_resources = await utils_docker.get_labelized_nodes_resources(
        app_settings.AUTOSCALING_MONITORED_NODES_LABELS
    )

    # NOTE: user_data is a script that gets launched when a new node is created
    assert app_settings.AUTOSCALING_AWS  # nosec
    user_data = utils_aws.compose_user_data(app_settings.AUTOSCALING_AWS)
