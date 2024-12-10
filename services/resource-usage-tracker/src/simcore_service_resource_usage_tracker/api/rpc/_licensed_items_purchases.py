from fastapi import FastAPI
from models_library.api_schemas_resource_usage_tracker.licensed_items_purchases import (
    LicensedItemPurchaseGet,
    LicensedItemsPurchasesPage,
)
from models_library.basic_types import IDStr
from models_library.products import ProductName
from models_library.resource_tracker_licensed_items_purchases import (
    LicensedItemPurchaseID,
    LicensedItemsPurchasesCreate,
)
from models_library.rest_ordering import OrderBy
from models_library.wallets import WalletID
from servicelib.rabbitmq import RPCRouter

from ...services import licensed_items_purchases

router = RPCRouter()


@router.expose(reraise_if_error_type=())
async def get_licensed_items_purchases_page(
    app: FastAPI,
    *,
    product_name: ProductName,
    wallet_id: WalletID,
    offset: int = 0,
    limit: int = 20,
    order_by: OrderBy = OrderBy(field=IDStr("purchased_at")),
) -> LicensedItemsPurchasesPage:
    return await licensed_items_purchases.list_licensed_items_purchases(
        db_engine=app.state.engine,
        product_name=product_name,
        offset=offset,
        limit=limit,
        filter_wallet_id=wallet_id,
        order_by=order_by,
    )


@router.expose(reraise_if_error_type=())
async def get_licensed_item_purchase(
    app: FastAPI,
    *,
    product_name: ProductName,
    licensed_item_purchase_id: LicensedItemPurchaseID,
) -> LicensedItemPurchaseGet:
    return await licensed_items_purchases.get_licensed_item_purchase(
        db_engine=app.state.engine,
        product_name=product_name,
        licensed_item_purchase_id=licensed_item_purchase_id,
    )


@router.expose(reraise_if_error_type=())
async def create_licensed_item_purchase(
    app: FastAPI, *, data: LicensedItemsPurchasesCreate
) -> LicensedItemPurchaseGet:
    return await licensed_items_purchases.create_licensed_item_purchase(
        db_engine=app.state.engine, data=data
    )
