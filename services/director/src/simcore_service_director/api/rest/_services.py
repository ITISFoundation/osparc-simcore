import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from models_library.generics import Envelope
from models_library.services_enums import ServiceType
from models_library.services_types import ServiceKey, ServiceVersion
from servicelib.fastapi.dependencies import get_app

from ... import exceptions, registry_proxy

router = APIRouter()

log = logging.getLogger(__name__)


@router.get("/services")
async def list_services(
    the_app: Annotated[FastAPI, Depends(get_app)],
    service_type: ServiceType | None = None,
) -> Envelope[list[dict[str, Any]]]:
    log.debug(
        "Client does list_services request with service_type %s",
        service_type,
    )
    try:
        services: list[dict[str, Any]] = []
        if not service_type:
            services = await registry_proxy.list_services(
                the_app, registry_proxy.ServiceType.ALL
            )
        elif "computational" in service_type:
            services = await registry_proxy.list_services(
                the_app, registry_proxy.ServiceType.COMPUTATIONAL
            )
        elif "interactive" in service_type:
            services = await registry_proxy.list_services(
                the_app, registry_proxy.ServiceType.DYNAMIC
            )
        # NOTE: the validation is done in the catalog. This entrypoint IS and MUST BE only used by the catalog!!
        # NOTE2: the catalog will directly talk to the registry see case #2165 [https://github.com/ITISFoundation/osparc-simcore/issues/2165]
        # services = node_validator.validate_nodes(services)
        return Envelope[list[dict[str, Any]]](data=services)
    except exceptions.RegistryConnectionError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=f"{err}"
        ) from err


@router.get("/services/{service_key:path}/{service_version}")
async def get_service(
    the_app: Annotated[FastAPI, Depends(get_app)],
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> Envelope[list[dict[str, Any]]]:
    log.debug(
        "Client does get_service with service_key %s, service_version %s",
        service_key,
        service_version,
    )
    try:
        services = [
            await registry_proxy.get_image_details(
                the_app, service_key, service_version
            )
        ]
        return Envelope[list[dict[str, Any]]](data=services)
    except exceptions.ServiceNotAvailableError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{err}"
        ) from err
    except exceptions.RegistryConnectionError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=f"{err}"
        ) from err


@router.get("/services/{service_key:path}/{service_version}/labels")
async def list_service_labels(
    the_app: Annotated[FastAPI, Depends(get_app)],
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> Envelope[dict[str, Any]]:
    log.debug(
        "Retrieving service labels with service_key %s, service_version %s",
        service_key,
        service_version,
    )
    try:
        service_labels, _ = await registry_proxy.get_image_labels(
            the_app, service_key, service_version
        )
        return Envelope[dict[str, Any]](data=service_labels)

    except exceptions.ServiceNotAvailableError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{err}"
        ) from err

    except exceptions.RegistryConnectionError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=f"{err}"
        ) from err
