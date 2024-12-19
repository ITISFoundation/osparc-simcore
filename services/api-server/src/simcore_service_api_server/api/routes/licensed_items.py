from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from pydantic import PositiveInt

from ...api.dependencies.authentication import get_current_user_id, get_product_name
from ...api.dependencies.webserver_rpc import get_wb_api_rpc_client
from ...exceptions.service_errors_utils import DEFAULT_BACKEND_SERVICE_STATUS_CODES
from ...models.pagination import Page, PaginationParams
from ...models.schemas.licensed_items import LicensedItemReleaseData
from ...models.schemas.model_adapter import LicensedItemCheckoutGet, LicensedItemGet
from ...services_rpc.wb_api_server import WbApiRpcClient

router = APIRouter()

_LICENSE_ITEMS_STATUS_CODES: dict[int | str, dict[str, Any]] = {
    **DEFAULT_BACKEND_SERVICE_STATUS_CODES,
}


@router.get(
    "",
    response_model=Page[LicensedItemGet],
    status_code=status.HTTP_200_OK,
    responses=_LICENSE_ITEMS_STATUS_CODES,
    description="Get all licensed items",
    include_in_schema=False,
)
async def get_licensed_items(
    page_params: Annotated[PaginationParams, Depends()],
    web_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    product_name: Annotated[str, Depends(get_product_name)],
):
    return await web_api_rpc.get_licensed_items(
        product_name=product_name, page_params=page_params
    )


@router.post(
    "release",
    response_model=LicensedItemCheckoutGet,
    status_code=status.HTTP_200_OK,
    responses=_LICENSE_ITEMS_STATUS_CODES,
    description="Release previously checked out licensed item",
    include_in_schema=False,
)
async def release_licensed_item(
    web_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    product_name: Annotated[str, Depends(get_product_name)],
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    licensed_item_release_data: LicensedItemReleaseData,
):
    return await web_api_rpc.release_licensed_item_for_wallet(
        product_name=product_name,
        user_id=user_id,
        licensed_item_checkout_id=licensed_item_release_data.licensed_item_checkout_id,
    )
