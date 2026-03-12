import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from models_library.api_schemas__common.health import HealthCheckGet
from models_library.errors import RABBITMQ_CLIENT_UNHEALTHY_MSG
from servicelib.rabbitmq import RabbitMQClient, RabbitMQRPCClient

from ...api.dependencies.rabbitmq import get_rabbitmq_client_from_request, rabbitmq_rpc_client


class HealthCheckError(RuntimeError):
    """Failed a health check"""


router = APIRouter()


@router.get("/", response_model=HealthCheckGet)
async def check_service_health(
    rabbitmq_client: Annotated[RabbitMQClient, Depends(get_rabbitmq_client_from_request)],
    rabbitmq_rpc: Annotated[RabbitMQRPCClient, Depends(rabbitmq_rpc_client)],
):
    if not rabbitmq_client.healthy or not rabbitmq_rpc.healthy:
        raise HealthCheckError(RABBITMQ_CLIENT_UNHEALTHY_MSG)

    return {"timestamp": f"{__name__}@{datetime.datetime.now(tz=datetime.UTC).isoformat()}"}
