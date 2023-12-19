import datetime
import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from servicelib.rabbitmq import RabbitMQClient

from ..modules.rabbitmq import get_rabbitmq_client_from_request

logger = logging.getLogger(__name__)


#
# ROUTE HANDLERS
#
router = APIRouter()


class HealthCheckError(RuntimeError):
    """Failed a health check"""


@router.get("/", response_class=PlainTextResponse)
async def healthcheck(
    rabbitmq_client: Annotated[
        RabbitMQClient, Depends(get_rabbitmq_client_from_request)
    ],
) -> str:
    if not rabbitmq_client.healthy:
        msg = "RabbitMQ client is in a bad state!"
        raise HealthCheckError(msg)

    return f"{__name__}@{datetime.datetime.now(datetime.timezone.utc).isoformat()}"
