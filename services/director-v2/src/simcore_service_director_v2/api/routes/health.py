from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def check_service_health() -> dict[str, str]:
    return {"timestamp": f"{__name__}@{datetime.now(timezone.utc).isoformat()}"}
