# pylint: disable=unused-argument
import urllib.parse
from typing import Optional

from fastapi import APIRouter, Depends, Path, Query, Response
from models_library.service_settings_labels import SimcoreServiceLabels
from models_library.services import KEY_RE, VERSION_RE, ServiceKeyVersion, ServiceType
from pydantic import constr

from ...models.schemas.services import ServiceExtrasEnveloped, ServicesArrayEnveloped
from ..dependencies.director_v0 import (
    DirectorV0Client,
    forward_to_director_v0,
    get_director_v0_client,
)

router = APIRouter()


@router.get(
    "",
    description="Lists services available in the deployed registry",
    response_model=ServicesArrayEnveloped,
)
async def list_services(
    service_type: Optional[ServiceType] = Query(
        None,
        description=(
            "The service type:\n"
            "   - computational - a computational service\n"
            "   - interactive - an interactive service\n"
        ),
    ),
    forward_request: Response = Depends(forward_to_director_v0),
):
    return forward_request


ServiceKeyPath = Path(
    ...,
    description="Distinctive name for the node based on the docker registry path",
    regex=KEY_RE,
)
ServiceKeyVersionPath = Path(
    ..., description="The tag/version of the service", regex=VERSION_RE
)


@router.get(
    "/{service_key:path}/{service_version}/extras",
    description="Returns the service extras",
    response_model=ServiceExtrasEnveloped,
)
async def get_extra_service_versioned(
    service_key: str = ServiceKeyPath,
    service_version: str = ServiceKeyVersionPath,
    forward_request: Response = Depends(forward_to_director_v0),
):
    return forward_request


@router.get(
    "/{service_key:path}/{service_version}",
    description="Returns details of the selected service if available in the platform",
    response_model=ServicesArrayEnveloped,
)
async def get_service_versioned(
    service_key: str = ServiceKeyPath,
    service_version: str = ServiceKeyVersionPath,
    forward_request: Response = Depends(forward_to_director_v0),
):
    return forward_request


@router.post(
    "/{service_key:path}/{service_version}/dynamic-sidecar:require",
    summary="returns True if service must be ran via dynamic-sidecar",
)
async def requires_dynamic_sidecar(
    service_key: str = constr(regex=KEY_RE, strip_whitespace=True),
    service_version: str = ServiceKeyVersionPath,
    director_v0_client: DirectorV0Client = Depends(get_director_v0_client),
) -> bool:
    simcore_service_labels: SimcoreServiceLabels = (
        await director_v0_client.get_service_labels(
            service=ServiceKeyVersion(
                key=urllib.parse.unquote_plus(service_key), version=service_version
            )
        )
    )
    return simcore_service_labels.needs_dynamic_sidecar
