
from typing import Optional

from fastapi import APIRouter, Path

from ...models.schemas.services import (
    SERVICE_IMAGE_NAME_RE,
    VERSION_RE,
    ServiceExtrasEnveloped,
    ServicesEnveloped,
    ServiceType,
)

router = APIRouter()


@router.get(
    "",
    description="Lists services available in the deployed registry",
    response_model=ServicesEnveloped,
)
async def list_services(service_type: Optional[ServiceType]):
    print(service_type)


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
    response_model=ServicesEnveloped,
)
async def get_service_versioned(
    service_key: str = ServiceKeyPath, service_version: str = ServiceKeyVersionPath
):
    pass


@router.get(
    "/{service_key}/{service_version}/extras",
    description="Currently returns the node_requirements an array of resoruces needed for scheduling",
    response_model=ServiceExtrasEnveloped,
)
async def get_extra_service_versioned(
    service_key: str = ServiceKeyPath, service_version: str = ServiceKeyVersionPath
):
    pass
