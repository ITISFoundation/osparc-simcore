import logging

from fastapi import FastAPI
from models_library.rabbitmq_messages import DynamicServiceRunningMessage
from pydantic import parse_raw_as

_logger = logging.getLogger(__name__)


async def process_dynamic_service_running_message(app: FastAPI, data: bytes) -> bool:
    assert app  # nosec
    rabbit_message: DynamicServiceRunningMessage = parse_raw_as(
        DynamicServiceRunningMessage, data  # type: ignore[arg-type]
    )
    _logger.info(
        "Process %s msg service_run_id: %s",
        rabbit_message.project_id,
        rabbit_message.node_id,
    )
    return True
