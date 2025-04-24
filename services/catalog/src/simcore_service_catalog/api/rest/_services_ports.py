import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from models_library.api_schemas_catalog.services_ports import ServicePortGet
from models_library.services_metadata_published import ServiceMetaDataPublished

from ..._constants import RESPONSE_MODEL_POLICY
from .._dependencies.services import (
    AccessInfo,
    check_service_read_access,
    get_service_from_manifest,
)

_logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/{service_key:path}/{service_version}/ports",
    response_model=list[ServicePortGet],
    description="Returns a list of service ports starting with inputs and followed by outputs",
    **RESPONSE_MODEL_POLICY,
)
async def list_service_ports(
    _user: Annotated[AccessInfo, Depends(check_service_read_access)],
    service: Annotated[ServiceMetaDataPublished, Depends(get_service_from_manifest)],
):
    ports: list[ServicePortGet] = []

    if service.inputs:
        for name, input_port in service.inputs.items():
            ports.append(
                ServicePortGet.from_domain_model(
                    kind="input", key=name, port=input_port
                )
            )

    if service.outputs:
        for name, output_port in service.outputs.items():
            ports.append(
                ServicePortGet.from_domain_model(
                    kind="output", key=name, port=output_port
                )
            )

    return ports
