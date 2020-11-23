# pylint: disable=unused-argument
from typing import Optional

from fastapi import APIRouter, Depends, Path, Query, Response
from models_library.services import KEY_RE, VERSION_RE, ServiceType

from ...models.schemas.services import ServiceExtrasEnveloped, ServicesArrayEnveloped
from ..dependencies.director_v0 import (
    forward_to_director_v0,
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
    description="Currently returns the node_requirements an array of resoruces needed for scheduling",
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
