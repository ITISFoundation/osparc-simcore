from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter()


@router.get("/", include_in_schema=False, response_class=PlainTextResponse)
async def check_service_health():
    return f"{__name__}@{datetime.now().isoformat()}"
