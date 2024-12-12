from typing import Annotated

from fastapi import APIRouter, Depends
from models_library.api_schemas_webserver.licensed_items import LicensedItemGetPage

from ...api.dependencies.authentication import get_product_name
from ...api.dependencies.webserver_rpc import get_wb_api_rpc_client
from ...models.pagination import PaginationParams
from ...services_rpc.wb_api_server import WbApiRpcClient

router = APIRouter()


@router.get(
    "/", response_model=LicensedItemGetPage, description="Get all licensed items"
)
async def get_licensed_items(
    page_params: Annotated[PaginationParams, Depends()],
    web_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    product_name: Annotated[str, Depends(get_product_name)],
) -> LicensedItemGetPage:
    return await web_api_rpc.get_licensed_items(
        product_name=product_name, page_params=page_params
    )
