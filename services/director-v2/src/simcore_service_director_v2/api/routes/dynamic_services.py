import logging
from typing import List

from fastapi import APIRouter, Depends
from models_library.projects_nodes import PROPERTY_KEY_RE
from pydantic import BaseModel
from starlette import status
from starlette.datastructures import URL

from ..dependencies.dynamic_services_v0 import (
    ServicesV0Client,
    get_service_base_url,
    get_services_v0_client,
)

router = APIRouter()
log = logging.getLogger(__file__)


class RetrieveDataIn(BaseModel):
    port_keys: List[PROPERTY_KEY_RE]


class RetrieveDataOut(BaseModel):
    size_bytes: int


class RequestResponse(BaseModel):
    data: RetrieveDataOut


@router.post(
    "/{node_uuid}:retrieve",
    summary="Calls the dynamic service's retrieve endpoint with optional port_keys",
    response_model=RequestResponse,
    status_code=status.HTTP_200_OK,
)
async def service_retrieve_data_on_ports(
    retrieve_settings: RetrieveDataIn,
    service_base_url: URL = Depends(get_service_base_url),
    services_client: ServicesV0Client = Depends(get_services_v0_client),
):
    return await services_client.request(
        "POST",
        f"{service_base_url}/request",
        data=retrieve_settings.json(by_alias=True),
    )
