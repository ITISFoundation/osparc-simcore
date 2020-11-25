import logging

from fastapi import APIRouter, Depends
from starlette import status
from starlette.datastructures import URL

from ...models.domains.dynamic_services import RetrieveDataIn, RetrieveDataOutEnveloped
from ...utils.logging_utils import log_decorator
from ..dependencies.dynamic_services import (
    ServicesClient,
    get_service_base_url,
    get_services_client,
)

router = APIRouter()
logger = logging.getLogger(__file__)


@router.post(
    "/{node_uuid}:retrieve",
    summary="Calls the dynamic service's retrieve endpoint with optional port_keys",
    response_model=RetrieveDataOutEnveloped,
    status_code=status.HTTP_200_OK,
)
@log_decorator(logger=logger)
async def service_retrieve_data_on_ports(
    retrieve_settings: RetrieveDataIn,
    service_base_url: URL = Depends(get_service_base_url),
    services_client: ServicesClient = Depends(get_services_client),
):
    # the handling of client/server errors is already encapsulated in the call to request
    resp = await services_client.request(
        "POST",
        f"{service_base_url}/retrieve",
        data=retrieve_settings.json(by_alias=True),
    )
    # validate and return
    return RetrieveDataOutEnveloped.parse_obj(resp.json())
