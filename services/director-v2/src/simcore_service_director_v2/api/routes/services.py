# pylint: disable=unused-argument

from typing import Optional

from fastapi import APIRouter, Path, Query, Depends

from ...models.schemas.services import (
    SERVICE_IMAGE_NAME_RE,
    VERSION_RE,
    ServiceExtrasEnveloped,
    ServicesArrayEnveloped,
    ServiceType,
)
from ..dependencies.director_v0 import ReverseProxyClient, get_reverse_proxy_to_v0


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
        director_v0: ReverseProxyClient = Depends(get_reverse_proxy_to_v0),

):
    # TODO: why service_type is optional??
    print(service_type)
    return director_v0.request(service_type)


ServiceKeyPath = Path(
    ...,
    description="Distinctive name for the node based on the docker registry path",
    regex=SERVICE_IMAGE_NAME_RE,
)
ServiceKeyVersionPath = Path(
    ..., description="The tag/version of the service", regex=VERSION_RE
)


@router.get(
    "/{service_key}/{service_version}",
    description="Returns details of the selected service if available in the platform",
    response_model=ServicesArrayEnveloped,
)
async def get_service_versioned(
    service_key: str = ServiceKeyPath, service_version: str = ServiceKeyVersionPath,
        director_v0: ReverseProxyClient = Depends(get_reverse_proxy_to_v0),

):
    return director_v0.request(service_key, service_version)


@router.get(
    "/{service_key}/{service_version}/extras",
    description="Currently returns the node_requirements an array of resoruces needed for scheduling",
    response_model=ServiceExtrasEnveloped,
)
async def get_extra_service_versioned(
    service_key: str = ServiceKeyPath, service_version: str = ServiceKeyVersionPath,
        director_v0: ReverseProxyClient = Depends(get_reverse_proxy_to_v0),

):
    return director_v0.request(service_key, service_version)
