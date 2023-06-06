# pylint: disable=unused-argument

from fastapi import APIRouter, Depends, Path, Query
from models_library.services import SERVICE_KEY_RE, VERSION_RE, ServiceType

from ...models.schemas.services import ServiceExtrasEnveloped, ServicesArrayEnveloped
from ..dependencies.director_v0 import Forwarded, forward_to_director_v0

router = APIRouter()


@router.get(
    "",
    description="Lists services available in the deployed registry",
    response_model=ServicesArrayEnveloped,
)
async def list_services(
    service_type: ServiceType
    | None = Query(
        None,
        description=(
            "The service type:\n"
            "   - computational - a computational service\n"
            "   - interactive - an interactive service\n"
        ),
    ),
    forward_request: Forwarded = Depends(forward_to_director_v0),
):
    return forward_request.response


ServiceKeyPath = Path(
    ...,
    description="Distinctive name for the node based on the docker registry path",
    regex=SERVICE_KEY_RE.pattern,
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
    forward_request: Forwarded = Depends(forward_to_director_v0),
):
    return forward_request.response


@router.get(
    "/{service_key:path}/{service_version}",
    description="Returns details of the selected service if available in the platform",
    response_model=ServicesArrayEnveloped,
)
async def get_service_versioned(
    service_key: str = ServiceKeyPath,
    service_version: str = ServiceKeyVersionPath,
    forward_request: Forwarded = Depends(forward_to_director_v0),
):
    return forward_request.response
