from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from models_library.licenses import LicensedItemID
from models_library.resource_tracker_license_checkouts import LicenseCheckoutID
from pydantic import PositiveInt
from simcore_service_api_server.api.dependencies.resource_usage_tracker_rpc import (
    get_resource_usage_tracker_client,
)

from ...api.dependencies.authentication import get_current_user_id, get_product_name
from ...api.dependencies.webserver_rpc import get_wb_api_rpc_client
from ...exceptions.service_errors_utils import DEFAULT_BACKEND_SERVICE_STATUS_CODES
from ...models.pagination import Page, PaginationParams
from ...models.schemas.model_adapter import LicensedItemCheckoutGet, LicensedItemGet
from ...services_rpc.resource_usage_tracker import ResourceUsageTrackerClient
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
    "/{licensed_item_id}/checked-out-items/{licensed_item_checkout_id}/release",
    response_model=LicensedItemCheckoutGet,
    status_code=status.HTTP_200_OK,
    responses=_LICENSE_ITEMS_STATUS_CODES,
    description="Release previously checked out licensed item",
)
async def release_licensed_item(
    web_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    rut_rpc: Annotated[
        ResourceUsageTrackerClient, Depends(get_resource_usage_tracker_client)
    ],
    product_name: Annotated[str, Depends(get_product_name)],
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    licensed_item_id: LicensedItemID,
    licensed_item_checkout_id: LicenseCheckoutID,
):
    _licensed_item_checkout = await rut_rpc.get_licensed_item_checkout(
        product_name=product_name, licensed_item_checkout_id=licensed_item_checkout_id
    )
    if _licensed_item_checkout.licensed_item_id != licensed_item_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{licensed_item_id} is not the license_item_id associated with the checked out item {licensed_item_checkout_id}",
        )
    return await web_api_rpc.release_licensed_item_for_wallet(
        product_name=product_name,
        user_id=user_id,
        licensed_item_checkout_id=licensed_item_checkout_id,
    )
