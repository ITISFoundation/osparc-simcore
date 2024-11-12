import logging

from fastapi import FastAPI
from models_library.rabbitmq_messages import RabbitResourceTrackingProjectSyncMessage
from pydantic import parse_raw_as

from .modules.db.repositories.resource_tracker import ResourceTrackerRepository
from .modules.rabbitmq import get_rabbitmq_client

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
    rabbitmq_client = get_rabbitmq_client(app)

    # UPDATE

    return True
