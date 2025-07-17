import logging
from typing import Annotated

import arrow
from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from models_library.errors import RABBITMQ_CLIENT_UNHEALTHY_MSG
from servicelib.rabbitmq import RabbitMQClient

from ...services.rabbitmq import get_rabbitmq_client_from_request

_logger = logging.getLogger(__name__)


class HealthCheckError(RuntimeError):
    """Failed a health check"""


router = APIRouter()


@router.get("/", response_class=PlainTextResponse)
async def healthcheck(
    rabbitmq_client: Annotated[
        RabbitMQClient, Depends(get_rabbitmq_client_from_request)
    ],
) -> str:
    _logger.debug("Checking rabbit health check %s", rabbitmq_client.healthy)
    if not rabbitmq_client.healthy:
        raise HealthCheckError(RABBITMQ_CLIENT_UNHEALTHY_MSG)

    return f"{__name__}@{arrow.utcnow().isoformat()}"
