import datetime

from fastapi import APIRouter
from models_library.api_schemas_directorv2 import HealthCheckGet

router = APIRouter()


@router.get("/", response_model=HealthCheckGet)
async def check_service_health():
    return {
        "timestamp": f"{__name__}@{datetime.datetime.now(tz=datetime.timezone.utc).isoformat()}"
    }
