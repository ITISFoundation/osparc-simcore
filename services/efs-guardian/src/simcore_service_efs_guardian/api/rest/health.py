"""
All entrypoints used for operations

for instance: service health-check (w/ different variants), diagnostics, debugging, status, etc
"""

import datetime

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter()


@router.get("/", include_in_schema=True, response_class=PlainTextResponse)
async def health_check():
    # NOTE: sync url in docker/healthcheck.py with this entrypoint!
    return f"{__name__}.health_check@{datetime.datetime.now(datetime.timezone.utc).isoformat()}"
