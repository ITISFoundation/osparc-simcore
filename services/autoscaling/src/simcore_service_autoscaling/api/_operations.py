"""
All entrypoints used for operations, for insteance
service health-check, diagnostics, debugging, status, etc
"""

import datetime

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter()


@router.get("/", include_in_schema=False, response_class=PlainTextResponse)
async def health_check():
    return f"{__name__}.health_check@{datetime.utcnow().isoformat()}"
