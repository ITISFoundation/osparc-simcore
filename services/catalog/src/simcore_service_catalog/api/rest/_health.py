import datetime

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def check_service_health():
    return f"{__name__}@{datetime.datetime.now(tz=datetime.UTC).isoformat()}"
