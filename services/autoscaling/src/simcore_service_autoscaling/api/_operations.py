"""
All entrypoints used for operations

for instance: service health-check (w/ different variants), diagnostics, debugging, status, etc
"""

from datetime import datetime

from fastapi import APIRouter, Depends, FastAPI
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from .dependencies.application import get_app

router = APIRouter()


@router.get("/", include_in_schema=True, response_class=PlainTextResponse)
async def health_check():
    # NOTE: sync url in docker/healthcheck.py with this entrypoint!
    return f"{__name__}.health_check@{datetime.utcnow().isoformat()}"


class StatusGet(BaseModel):
    rabbitmq: str


@router.get("/status", include_in_schema=True, response_model=StatusGet)
async def get_status(app: FastAPI = Depends(get_app)) -> StatusGet:
    return StatusGet(
        rabbitmq="connected" if app.state.rabbitmq_client else "not connected"
    )
