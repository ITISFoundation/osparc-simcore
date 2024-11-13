import logging

from fastapi import FastAPI
from models_library.rabbitmq_messages import RabbitResourceTrackingProjectSyncMessage
from pydantic import parse_raw_as

from .modules.db.repositories.resource_tracker import ResourceTrackerRepository
from .utils import convert_project_tags_to_db

_logger = logging.getLogger(__name__)


async def process_message(app: FastAPI, data: bytes) -> bool:
    rabbit_message: RabbitResourceTrackingProjectSyncMessage = parse_raw_as(
        RabbitResourceTrackingProjectSyncMessage, data  # type: ignore[arg-type]
    )
    _logger.info(
        "Process project sync msg for project ID: %s",
        rabbit_message.project_id,
    )
    resource_tracker_repo: ResourceTrackerRepository = ResourceTrackerRepository(
        db_engine=app.state.engine
    )

    # UPDATE
    if rabbit_message.project_tags:
        project_tags_db = await convert_project_tags_to_db(rabbit_message.project_tags)
    else:
        project_tags_db = None

    await resource_tracker_repo.update_rut_project_metadata(
        rabbit_message.project_id,
        project_name=rabbit_message.project_name,
        project_tags=project_tags_db,
    )

    return True
