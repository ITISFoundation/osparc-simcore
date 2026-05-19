"""
All entrypoints used for operations

for instance: service health-check (w/ different variants), diagnostics, debugging, status, etc
"""

import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, status
from fastapi.responses import PlainTextResponse
from models_library.errors import RABBITMQ_CLIENT_UNHEALTHY_MSG, REDIS_CLIENT_UNHEALTHY_MSG
from servicelib.fastapi.dependencies import get_app

from ...services.modules.rabbitmq import get_rabbitmq_client, get_rabbitmq_rpc_client
from ...services.modules.redis import get_redis_lock_client

router = APIRouter()


@router.get("/", include_in_schema=True, response_class=PlainTextResponse)
async def health_check(
    app: Annotated[FastAPI, Depends(get_app)],
):
    if not get_rabbitmq_client(app).healthy or not get_rabbitmq_rpc_client(app).healthy:
        return PlainTextResponse(
            RABBITMQ_CLIENT_UNHEALTHY_MSG,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    if not get_redis_lock_client(app).is_healthy:
        return PlainTextResponse(
            REDIS_CLIENT_UNHEALTHY_MSG,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    # NOTE: sync url in docker/healthcheck.py with this entrypoint!
    return f"{__name__}.health_check@{datetime.datetime.now(datetime.UTC).isoformat()}"
