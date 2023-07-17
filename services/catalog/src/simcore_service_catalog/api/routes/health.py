import datetime

from fastapi import APIRouter

router = APIRouter()


@router.get("/", include_in_schema=False)
async def check_service_health():
    return f"{__name__}@{datetime.datetime.now(tz=datetime.timezone.utc).isoformat()}"
