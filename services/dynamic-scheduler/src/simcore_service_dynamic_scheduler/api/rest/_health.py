import logging

import arrow
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

_logger = logging.getLogger(__name__)


router = APIRouter()


@router.get("/", response_class=PlainTextResponse)
async def healthcheck():
    return f"{__name__}@{arrow.utcnow().isoformat()}"
