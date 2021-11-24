from datetime import datetime
from typing import Dict

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def check_service_health() -> Dict[str, str]:
    return {"timestamp": f"{__name__}@{datetime.utcnow().isoformat()}"}
