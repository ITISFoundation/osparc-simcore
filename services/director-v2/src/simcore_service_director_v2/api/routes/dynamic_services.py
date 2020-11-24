import logging
from typing import List

from fastapi import APIRouter, Depends
from models_library.projects_nodes import PROPERTY_KEY_RE, NodeID
from pydantic import BaseModel
from starlette import status


from ..dependencies.dynamic_services_v0 import ServicesV0Client, get_services_v0_client

router = APIRouter()
log = logging.getLogger(__file__)


class RetrieveDataIn(BaseModel):
    port_keys: List[PROPERTY_KEY_RE]


@router.post(
    "/{node_uuid}:retrieve",
    summary="Calls the dynamic service's retrieve endpoint with optional port_keys",
    response_model=None,
    status_code=status.HTTP_200_OK,
)
async def service_retrieve_data_on_ports(
    node_uuid: NodeID,
    retrieve_settings: RetrieveDataIn,
    services_client: ServicesV0Client = Depends(get_services_v0_client),
):
    node_details = await director_client.get_running_service_details(node_uuid)
    await services_client.call_retrieve(retrieve_settings.port_keys)
