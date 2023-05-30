import datetime
import logging

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

logger = logging.getLogger(__name__)


#
# ROUTE HANDLERS
#
router = APIRouter()


@router.get("/", response_class=PlainTextResponse)
async def healthcheck() -> str:
    return f"{__name__}@{datetime.datetime.now(datetime.timezone.utc).isoformat()}"
