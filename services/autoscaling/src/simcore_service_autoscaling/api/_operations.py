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


class RabbitMQStatus(BaseModel):
    initialized: bool
    connection_state: bool

    @classmethod
    def from_app(cls, app: FastAPI) -> "RabbitMQStatus":
        if app.state.rabbitmq_client:
            client = get_rabbitmq_client(app)

        # TODO: ping the rabbit MQ
        return RabbitMQStatus(
            initialized=bool(app.state.rabbitmq_client), connection_state=False
        )


class StatusGet(BaseModel):
    rabbitmq: RabbitMQStatus


@router.get("/status", include_in_schema=True, response_model=StatusGet)
async def get_status(app: FastAPI = Depends(get_app)) -> StatusGet:
    return StatusGet(rabbitmq=RabbitMQStatus.from_app(app))
