"""
All entrypoints used for operations

for instance: service health-check (w/ different variants), diagnostics, debugging, status, etc
"""

import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI
from fastapi.responses import PlainTextResponse
from models_library.errors import RABBITMQ_CLIENT_UNHEALTHY_MSG
from servicelib.fastapi.dependencies import get_app

from ...services.modules.rabbitmq import get_rabbitmq_client, get_rabbitmq_rpc_client

router = APIRouter()


class HealthCheckError(RuntimeError):
    """Failed a health check"""


@router.get("/", include_in_schema=True, response_class=PlainTextResponse)
async def health_check(
    app: Annotated[FastAPI, Depends(get_app)],
):
    if any(not client.healthy for client in (get_rabbitmq_client(app), get_rabbitmq_rpc_client(app))):
        raise HealthCheckError(RABBITMQ_CLIENT_UNHEALTHY_MSG)

    # NOTE: sync url in docker/healthcheck.py with this entrypoint!
    return f"{__name__}.health_check@{datetime.datetime.now(datetime.UTC).isoformat()}"
