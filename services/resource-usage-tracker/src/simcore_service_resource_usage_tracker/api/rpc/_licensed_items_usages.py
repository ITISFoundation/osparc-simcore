from fastapi import FastAPI
from models_library.api_schemas_resource_usage_tracker.licensed_items_usages import (
    LicenseCheckoutGet,
    LicenseCheckoutID,
    LicensedItemsUsagesPage,
    LicensedItemUsageGet,
)
from models_library.licensed_items import LicensedItemID
from models_library.products import ProductName
from models_library.resource_tracker import ServiceRunId
from models_library.resource_tracker_licensed_items_usages import LicensedItemUsageID
from models_library.rest_ordering import OrderBy
from models_library.users import UserID
from models_library.wallets import WalletID
from servicelib.rabbitmq import RPCRouter

from ...services import licensed_items_usages

router = RPCRouter()


@router.expose(reraise_if_error_type=())
async def get_licensed_item_usage(
    app: FastAPI,
    *,
    product_name: ProductName,
    licensed_item_usage_id: LicensedItemUsageID,
) -> LicensedItemUsageGet:
    return await licensed_items_usages.get_licensed_item_usage(
        db_engine=app.state.engine,
        product_name=product_name,
        licensed_item_usage_id=licensed_item_usage_id,
    )


@router.expose(reraise_if_error_type=())
async def get_licensed_items_usages_page(
    app: FastAPI,
    *,
    product_name: ProductName,
    filter_wallet_id: WalletID,
    offset: int = 0,
    limit: int = 20,
    order_by: OrderBy,
) -> LicensedItemsUsagesPage:
    return await licensed_items_usages.list_licensed_items_usages(
        db_engine=app.state.engine,
        product_name=product_name,
        filter_wallet_id=filter_wallet_id,
        offset=offset,
        limit=limit,
        order_by=order_by,
    )


@router.expose(reraise_if_error_type=())
async def checkout_licensed_item(
    app: FastAPI,
    *,
    licensed_item_id: LicensedItemID,
    wallet_id: WalletID,
    product_name: ProductName,
    num_of_seats: int,
    service_run_id: ServiceRunId,
    user_id: UserID,
    user_email: str,
) -> LicenseCheckoutGet:
    return await licensed_items_usages.checkout_licensed_item(
        db_engine=app.state.engine,
        licensed_item_id=licensed_item_id,
        wallet_id=wallet_id,
        product_name=product_name,
        num_of_seats=num_of_seats,
        service_run_id=service_run_id,
        user_id=user_id,
        user_email=user_email,
    )


@router.expose(reraise_if_error_type=())
async def release_licensed_item(
    app: FastAPI, *, checkout_id: LicenseCheckoutID, product_name: ProductName
) -> LicensedItemUsageGet:
    return await licensed_items_usages.release_licensed_item(
        db_engine=app.state.engine, checkout_id=checkout_id, product_name=product_name
    )
