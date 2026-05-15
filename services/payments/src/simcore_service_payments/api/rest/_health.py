import logging
from typing import Annotated

import arrow
from fastapi import APIRouter, Depends, status
from fastapi.responses import PlainTextResponse
from models_library.errors import RABBITMQ_CLIENT_UNHEALTHY_MSG
from servicelib.rabbitmq import RabbitMQClient, RabbitMQRPCClient

from ...services.rabbitmq import get_rabbitmq_client_from_request, get_rabbitmq_rpc_client_from_request

_logger = logging.getLogger(__name__)


router = APIRouter()


@router.get("/", response_class=PlainTextResponse)
async def healthcheck(
    rabbitmq_client: Annotated[RabbitMQClient, Depends(get_rabbitmq_client_from_request)],
    rabbitmq_rpc_client: Annotated[RabbitMQRPCClient, Depends(get_rabbitmq_rpc_client_from_request)],
) -> str | PlainTextResponse:
    if not rabbitmq_client.healthy or not rabbitmq_rpc_client.healthy:
        return PlainTextResponse(
            RABBITMQ_CLIENT_UNHEALTHY_MSG,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return f"{__name__}@{arrow.utcnow().isoformat()}"
