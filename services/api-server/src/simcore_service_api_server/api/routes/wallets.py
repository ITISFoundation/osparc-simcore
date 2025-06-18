import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from models_library.licenses import LicensedItemID
from pydantic import PositiveInt

from ...api.dependencies.authentication import get_current_user_id, get_product_name
from ...api.dependencies.webserver_rpc import get_wb_api_rpc_client
from ...exceptions.service_errors_utils import DEFAULT_BACKEND_SERVICE_STATUS_CODES
from ...models.pagination import Page, PaginationParams
from ...models.schemas.errors import ErrorGet
from ...models.schemas.licensed_items import LicensedItemCheckoutData
from ...models.schemas.model_adapter import (
    LicensedItemCheckoutGet,
    LicensedItemGet,
    WalletGetWithAvailableCreditsLegacy,
)
from ...services_rpc.wb_api_server import WbApiRpcClient
from ..dependencies.webserver_http import AuthSession, get_webserver_session
from ._constants import FMSG_CHANGELOG_NEW_IN_VERSION, create_route_description

_logger = logging.getLogger(__name__)

router = APIRouter()

WALLET_STATUS_CODES: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {
        "description": "Wallet not found",
        "model": ErrorGet,
    },
    status.HTTP_403_FORBIDDEN: {
        "description": "Access to wallet is not allowed",
        "model": ErrorGet,
    },
    **DEFAULT_BACKEND_SERVICE_STATUS_CODES,
}


@router.get(
    "/default",
    description=create_route_description(
        base="Get default wallet",
        changelog=[
            FMSG_CHANGELOG_NEW_IN_VERSION.format("0.7"),
        ],
    ),
    response_model=WalletGetWithAvailableCreditsLegacy,
    responses=WALLET_STATUS_CODES,
)
async def get_default_wallet(
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
):
    return await webserver_api.get_default_wallet()


@router.get(
    "/{wallet_id}",
    response_model=WalletGetWithAvailableCreditsLegacy,
    responses=WALLET_STATUS_CODES,
    description=create_route_description(
        base="Get wallet",
        changelog=[
            FMSG_CHANGELOG_NEW_IN_VERSION.format("0.7"),
        ],
    ),
)
async def get_wallet(
    wallet_id: int,
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
):
    return await webserver_api.get_wallet(wallet_id=wallet_id)


@router.get(
    "/{wallet_id}/licensed-items",
    response_model=Page[LicensedItemGet],
    status_code=status.HTTP_200_OK,
    responses=WALLET_STATUS_CODES,
    description=create_route_description(
        base="Get all available licensed items for a given wallet",
        changelog=[
            FMSG_CHANGELOG_NEW_IN_VERSION.format("0.6"),
        ],
    ),
)
async def get_available_licensed_items_for_wallet(
    wallet_id: int,
    page_params: Annotated[PaginationParams, Depends()],
    web_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    product_name: Annotated[str, Depends(get_product_name)],
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
):
    return await web_api_rpc.get_available_licensed_items_for_wallet(
        product_name=product_name,
        wallet_id=wallet_id,
        user_id=user_id,
        page_params=page_params,
    )


@router.post(
    "/{wallet_id}/licensed-items/{licensed_item_id}/checkout",
    response_model=LicensedItemCheckoutGet,
    status_code=status.HTTP_200_OK,
    responses=WALLET_STATUS_CODES,
    description="Checkout licensed item",
)
async def checkout_licensed_item(
    wallet_id: int,
    licensed_item_id: LicensedItemID,
    web_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    product_name: Annotated[str, Depends(get_product_name)],
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    checkout_data: LicensedItemCheckoutData,
):
    return await web_api_rpc.checkout_licensed_item_for_wallet(
        product_name=product_name,
        user_id=user_id,
        wallet_id=wallet_id,
        licensed_item_id=licensed_item_id,
        num_of_seats=checkout_data.number_of_seats,
        service_run_id=checkout_data.service_run_id,
    )
