import logging
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, status
from models_library.generics import Envelope
from models_library.projects import ProjectID
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID
from servicelib.fastapi.dependencies import get_app

from ... import producer
from ...core.errors import (
    RegistryConnectionError,
    ServiceNotAvailableError,
    ServiceUUIDInUseError,
    ServiceUUIDNotFoundError,
)

router = APIRouter()

_logger = logging.getLogger(__name__)


@router.get("/running_interactive_services")
async def list_running_services(
    the_app: Annotated[FastAPI, Depends(get_app)],
    user_id: UserID | None = None,
    project_id: ProjectID | None = None,
) -> Envelope[list[dict[str, Any]]]:
    _logger.debug(
        "Client does list_running_services request user_id %s, project_id %s",
        user_id,
        project_id,
    )
    services = await producer.get_services_details(
        the_app,
        f"{user_id}" if user_id else None,
        f"{project_id}" if project_id else None,
    )
    return Envelope[list[dict[str, Any]]](data=services)


@router.post(
    "/running_interactive_services",
    status_code=status.HTTP_201_CREATED,
)
async def start_service(
    the_app: Annotated[FastAPI, Depends(get_app)],
    user_id: UserID,
    project_id: ProjectID,
    service_key: ServiceKey,
    service_uuid: UUID,
    service_basepath: Path = Path(),
    service_tag: ServiceVersion | None = None,
    x_simcore_user_agent: str = Header(...),
) -> Envelope[dict[str, Any]]:
    _logger.debug(
        "Client does start_service with user_id %s, project_id %s, service %s:%s, service_uuid %s, service_basepath %s, request_simcore_user_agent %s",
        user_id,
        project_id,
        service_key,
        service_tag,
        service_uuid,
        service_basepath,
        x_simcore_user_agent,
    )
    try:
        service = await producer.start_service(
            the_app,
            f"{user_id}",
            f"{project_id}",
            service_key,
            service_tag,
            f"{service_uuid}",
            f"{service_basepath}",
            x_simcore_user_agent,
        )
        return Envelope[dict[str, Any]](data=service)
    except ServiceNotAvailableError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{err}"
        ) from err
    except ServiceUUIDInUseError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"{err}"
        ) from err
    except RegistryConnectionError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=f"{err}"
        ) from err


@router.get("/running_interactive_services/{service_uuid}")
async def get_running_service(
    the_app: Annotated[FastAPI, Depends(get_app)],
    service_uuid: UUID,
) -> Envelope[dict[str, Any]]:
    _logger.debug(
        "Client does get_running_service with service_uuid %s",
        service_uuid,
    )
    try:
        service = await producer.get_service_details(the_app, f"{service_uuid}")
        return Envelope[dict[str, Any]](data=service)
    except ServiceUUIDNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{err}"
        ) from err


@router.delete(
    "/running_interactive_services/{service_uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def stop_service(
    the_app: Annotated[FastAPI, Depends(get_app)],
    service_uuid: UUID,
    save_state: bool = True,
) -> None:
    _logger.debug(
        "Client does stop_service with service_uuid %s",
        service_uuid,
    )
    try:
        await producer.stop_service(
            the_app, node_uuid=f"{service_uuid}", save_state=save_state
        )

    except ServiceUUIDNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{err}"
        ) from err
