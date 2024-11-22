import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from models_library.generics import Envelope
from models_library.services_types import ServiceKey, ServiceVersion
from servicelib.fastapi.dependencies import get_app

from ... import registry_proxy
from ...core.errors import RegistryConnectionError, ServiceNotAvailableError

router = APIRouter()

_logger = logging.getLogger(__name__)


@router.get("/service_extras/{service_key:path}/{service_version}")
async def list_service_extras(
    the_app: Annotated[FastAPI, Depends(get_app)],
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> Envelope[dict[str, Any]]:
    _logger.debug(
        "Client does service_extras_by_key_version_get request with service_key %s, service_version %s",
        service_key,
        service_version,
    )
    try:
        service_extras = await registry_proxy.get_service_extras(
            the_app, service_key, service_version
        )
        return Envelope[dict[str, Any]](data=service_extras)
    except ServiceNotAvailableError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{err}"
        ) from err
    except RegistryConnectionError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=f"{err}"
        ) from err
