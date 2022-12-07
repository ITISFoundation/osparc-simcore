"""
All entrypoints used for operations

for instance: service health-check (w/ different variants), diagnostics, debugging, status, etc
"""

from datetime import datetime

from fastapi import APIRouter, Depends, FastAPI
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from ..modules.rabbitmq import get_rabbitmq_client
from .dependencies.application import get_app

router = APIRouter()


@router.get("/", include_in_schema=True, response_class=PlainTextResponse)
async def health_check():
    # NOTE: sync url in docker/healthcheck.py with this entrypoint!
    return f"{__name__}.health_check@{datetime.utcnow().isoformat()}"


class _ComponentStatus(BaseModel):
    initialized: bool
    connection_state: bool


class _RabbitMQStatus(_ComponentStatus):
    ...


class _EC2Status(_ComponentStatus):
    ...


class _StatusGet(BaseModel):
    rabbitmq: _RabbitMQStatus
    ec2: _EC2Status


@router.get("/status", include_in_schema=True, response_model=_StatusGet)
async def get_status(app: FastAPI = Depends(get_app)) -> _StatusGet:

    return _StatusGet(
        rabbitmq=_RabbitMQStatus(
            initialized=bool(app.state.rabbitmq_client),
            connection_state=await get_rabbitmq_client(app).ping()
            if app.state.rabbitmq_client
            else False,
        ),
        ec2=_EC2Status(
            initialized=bool(app.state.ec2_client),
            connection_state=await app.state.ec2_client.ping()
            if app.state.ec2_client
            else False,
        ),
    )
