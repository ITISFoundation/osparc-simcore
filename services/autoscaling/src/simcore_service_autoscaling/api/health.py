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
    is_enabled: bool
    is_responsive: bool


class _StatusGet(BaseModel):
    rabbitmq: _ComponentStatus
    ec2: _ComponentStatus
    docker: _ComponentStatus


@router.get("/status", include_in_schema=True, response_model=_StatusGet)
async def get_status(app: FastAPI = Depends(get_app)) -> _StatusGet:

    return _StatusGet(
        rabbitmq=_ComponentStatus(
            is_enabled=bool(app.state.rabbitmq_client),
            is_responsive=await get_rabbitmq_client(app).ping()
            if app.state.rabbitmq_client
            else False,
        ),
        ec2=_ComponentStatus(
            is_enabled=bool(app.state.ec2_client),
            is_responsive=await app.state.ec2_client.ping()
            if app.state.ec2_client
            else False,
        ),
        docker=_ComponentStatus(
            is_enabled=bool(app.state.docker_client),
            is_responsive=await app.state.docker_client.ping()
            if app.state.docker_client
            else False,
        ),
    )
