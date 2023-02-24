from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter()


@router.get("/", include_in_schema=False)
async def check_service_health():
    return f"{__name__}@{datetime.now(timezone.utc).replace(tzinfo=None).isoformat()}"
