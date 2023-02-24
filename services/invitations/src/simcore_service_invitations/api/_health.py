import logging
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

logger = logging.getLogger(__name__)


#
# ROUTE HANDLERS
#
router = APIRouter()


@router.get("/", response_class=PlainTextResponse)
async def healthcheck():
    return f"{__name__}@{datetime.now(timezone.utc).replace(tzinfo=None).isoformat()}"
