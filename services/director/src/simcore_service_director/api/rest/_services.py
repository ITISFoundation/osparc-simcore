import arrow
from fastapi import APIRouter
from models_library.services_enums import ServiceType
from models_library.services_types import ServiceKey, ServiceVersion

router = APIRouter()


@router.get("/services")
async def list_services(service_type: ServiceType | None = None):
    # NOTE: sync url in docker/healthcheck.py with this entrypoint!
    return f"{__name__}.health_check@{arrow.utcnow().isoformat()}"


@router.get("/services/{service_key}/{service_version}")
async def get_service(
    service_key: ServiceKey,
    service_version: ServiceVersion,
):
    # NOTE: sync url in docker/healthcheck.py with this entrypoint!
    return f"{__name__}.health_check@{arrow.utcnow().isoformat()}"


@router.get("/services/{service_key}/{service_version}/labels")
async def list_service_labels(
    service_key: ServiceKey,
    service_version: ServiceVersion,
):
    # NOTE: sync url in docker/healthcheck.py with this entrypoint!
    return f"{__name__}.health_check@{arrow.utcnow().isoformat()}"
