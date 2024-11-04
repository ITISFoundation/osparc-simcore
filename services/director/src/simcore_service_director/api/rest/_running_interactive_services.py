from pathlib import Path
from uuid import UUID

import arrow
from fastapi import APIRouter
from models_library.projects import ProjectID
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID

router = APIRouter()


@router.get("/running_interactive_services")
async def list_running_services(user_id: UserID, project_id: ProjectID):
    # NOTE: sync url in docker/healthcheck.py with this entrypoint!
    return f"{__name__}.health_check@{arrow.utcnow().isoformat()}"


@router.post("/running_interactive_services")
async def start_service(
    user_id: UserID,
    project_id: ProjectID,
    service_key: ServiceKey,
    service_uuid: UUID,
    service_basepath: Path,
    service_tag: ServiceVersion | None = None,
):
    # NOTE: sync url in docker/healthcheck.py with this entrypoint!
    return f"{__name__}.health_check@{arrow.utcnow().isoformat()}"


@router.get("/running_interactive_services/{service_uuid}")
async def get_running_service(service_uuid: UUID):
    # NOTE: sync url in docker/healthcheck.py with this entrypoint!
    return f"{__name__}.health_check@{arrow.utcnow().isoformat()}"


@router.delete("/running_interactive_services/{service_uuid}")
async def stop_service(service_uuid: UUID):
    # NOTE: sync url in docker/healthcheck.py with this entrypoint!
    return f"{__name__}.health_check@{arrow.utcnow().isoformat()}"
