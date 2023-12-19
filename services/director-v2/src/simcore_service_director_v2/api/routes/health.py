import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from models_library.api_schemas_directorv2.health import HealthCheckGet
from servicelib.rabbitmq import RabbitMQClient

from ...modules.rabbitmq import get_rabbitmq_client_from_request


class HealthCheckError(RuntimeError):
    """Failed a health check"""


router = APIRouter()


@router.get("/", response_model=HealthCheckGet)
async def check_service_health(
    rabbitmq_client: Annotated[
        RabbitMQClient, Depends(get_rabbitmq_client_from_request)
    ]
):
    if not rabbitmq_client.healthy:
        msg = "RabbitMQ client is in a bad state!"
        raise HealthCheckError(msg)

    return {
        "timestamp": f"{__name__}@{datetime.datetime.now(tz=datetime.timezone.utc).isoformat()}"
    }
