"""
All entrypoints used for operations

for instance: service health-check (w/ different variants), diagnostics, debugging, status, etc
"""

from datetime import datetime

from fastapi import APIRouter, Depends, FastAPI
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from ..rabbitmq import get_rabbitmq_client
from .dependencies.application import get_app

router = APIRouter()


@router.get("/", include_in_schema=True, response_class=PlainTextResponse)
async def health_check():
    # NOTE: sync url in docker/healthcheck.py with this entrypoint!
    return f"{__name__}.health_check@{datetime.utcnow().isoformat()}"


class _RabbitMQStatus(BaseModel):
    initialized: bool
    connection_state: bool


class _StatusGet(BaseModel):
    rabbitmq: _RabbitMQStatus


@router.get("/status", include_in_schema=True, response_model=_StatusGet)
async def get_status(app: FastAPI = Depends(get_app)) -> _StatusGet:

    return _StatusGet(
        rabbitmq=_RabbitMQStatus(
            initialized=bool(app.state.rabbitmq_client),
            connection_state=await get_rabbitmq_client(app).ping()
            if app.state.rabbitmq_client
            else False,
        )
    )
