from typing import Annotated

from fastapi import APIRouter, Depends
from models_library.api_schemas_webserver.licensed_items import LicensedItemGetPage
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.webserver.licenses.licensed_items import (
    get_licensed_items as _get_licensed_items,
)
from simcore_service_api_server.api.dependencies.authentication import get_product_name
from simcore_service_api_server.api.dependencies.rabbitmq import get_rabbitmq_rpc_client
from simcore_service_api_server.models.pagination import PaginationParams

router = APIRouter()


@router.get(
    "/", response_model=LicensedItemGetPage, description="Get all licensed items"
)
async def get_licensed_items(
    wallet_id: int,
    page_params: Annotated[PaginationParams, Depends()],
    webserver_rpc_api: Annotated[RabbitMQRPCClient, Depends(get_rabbitmq_rpc_client)],
    product_name: Annotated[str, Depends(get_product_name)],
) -> LicensedItemGetPage:
    return await _get_licensed_items(
        rabbitmq_rpc_client=webserver_rpc_api,
        product_name=product_name,
    )
