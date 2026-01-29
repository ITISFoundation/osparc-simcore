import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI
from models_library.errors import RABBITMQ_CLIENT_UNHEALTHY_MSG
from servicelib.fastapi.dependencies import get_app

from ...clients.rabbitmq import get_rabbitmq_rpc_client

router = APIRouter()


class HealthCheckError(RuntimeError):
    """Failed a health check"""


@router.get("/")
async def check_service_health(
    app: Annotated[FastAPI, Depends(get_app)],
):
    if not get_rabbitmq_rpc_client(app).healthy:
        raise HealthCheckError(RABBITMQ_CLIENT_UNHEALTHY_MSG)
    return f"{__name__}@{datetime.datetime.now(tz=datetime.UTC).isoformat()}"
