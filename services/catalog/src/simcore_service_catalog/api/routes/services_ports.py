import logging

from fastapi import APIRouter, Depends
from models_library.api_schemas_catalog.constants import RESPONSE_MODEL_POLICY
from models_library.api_schemas_catalog.services import ServiceGet
from models_library.api_schemas_catalog.services_ports import ServicePortGet

from ..dependencies.services import (
    AccessInfo,
    check_service_read_access,
    get_service_from_registry,
)

_logger = logging.getLogger(__name__)


#
# Routes -----------------------------------------------------------------------------------------------
#

router = APIRouter()


@router.get(
    "/{service_key:path}/{service_version}/ports",
    response_model=list[ServicePortGet],
    description="Returns a list of service ports starting with inputs and followed by outputs",
    **RESPONSE_MODEL_POLICY,
)
async def list_service_ports(
    _user: AccessInfo = Depends(check_service_read_access),
    service: ServiceGet = Depends(get_service_from_registry),
):
    ports: list[ServicePortGet] = []

    if service.inputs:
        for name, port in service.inputs.items():
            ports.append(ServicePortGet.from_service_io("input", name, port))

    if service.outputs:
        for name, port in service.outputs.items():
            ports.append(ServicePortGet.from_service_io("output", name, port))

    return ports
