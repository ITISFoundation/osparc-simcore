import arrow
from fastapi import APIRouter
from models_library.services_types import ServiceKey, ServiceVersion

router = APIRouter()


@router.get("/service_extras/{service_key}/{service_version}")
async def list_service_extras(
    service_key: ServiceKey,
    service_version: ServiceVersion,
):
    # NOTE: sync url in docker/healthcheck.py with this entrypoint!
    return f"{__name__}.health_check@{arrow.utcnow().isoformat()}"
