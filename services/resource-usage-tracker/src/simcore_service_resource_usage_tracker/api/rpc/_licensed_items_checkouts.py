from fastapi import FastAPI
from models_library.api_schemas_resource_usage_tracker.licensed_items_checkouts import (
    LicensedItemCheckoutGet,
    LicensedItemsCheckoutsPage,
)
from models_library.licensed_items import LicensedItemID
from models_library.products import ProductName
from models_library.resource_tracker import ServiceRunId
from models_library.resource_tracker_licensed_items_checkouts import (
    LicensedItemCheckoutID,
)
from models_library.rest_ordering import OrderBy
from models_library.users import UserID
from models_library.wallets import WalletID
from servicelib.rabbitmq import RPCRouter
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker.errors import (
    LICENSES_ERRORS,
)

from ...services import licensed_items_checkouts

router = RPCRouter()


@router.expose(reraise_if_error_type=LICENSES_ERRORS)
async def get_licensed_item_checkout(
    app: FastAPI,
    *,
    product_name: ProductName,
    licensed_item_checkout_id: LicensedItemCheckoutID,
) -> LicensedItemCheckoutGet:
    return await licensed_items_checkouts.get_licensed_item_checkout(
        db_engine=app.state.engine,
        product_name=product_name,
        licensed_item_checkout_id=licensed_item_checkout_id,
    )


@router.expose(reraise_if_error_type=LICENSES_ERRORS)
async def get_licensed_items_checkouts_page(
    app: FastAPI,
    *,
    product_name: ProductName,
    filter_wallet_id: WalletID,
    offset: int = 0,
    limit: int = 20,
    order_by: OrderBy,
) -> LicensedItemsCheckoutsPage:
    return await licensed_items_checkouts.list_licensed_items_checkouts(
        db_engine=app.state.engine,
        product_name=product_name,
        filter_wallet_id=filter_wallet_id,
        offset=offset,
        limit=limit,
        order_by=order_by,
    )


@router.expose(reraise_if_error_type=LICENSES_ERRORS)
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
) -> LicensedItemCheckoutGet:
    return await licensed_items_checkouts.checkout_licensed_item(
        db_engine=app.state.engine,
        licensed_item_id=licensed_item_id,
        wallet_id=wallet_id,
        product_name=product_name,
        num_of_seats=num_of_seats,
        service_run_id=service_run_id,
        user_id=user_id,
        user_email=user_email,
    )


@router.expose(reraise_if_error_type=LICENSES_ERRORS)
async def release_licensed_item(
    app: FastAPI,
    *,
    licensed_item_checkout_id: LicensedItemCheckoutID,
    product_name: ProductName,
) -> LicensedItemCheckoutGet:
    return await licensed_items_checkouts.release_licensed_item(
        db_engine=app.state.engine,
        licensed_item_checkout_id=licensed_item_checkout_id,
        product_name=product_name,
    )
