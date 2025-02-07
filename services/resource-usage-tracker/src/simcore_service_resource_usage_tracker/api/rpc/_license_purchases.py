from fastapi import FastAPI
from models_library.api_schemas_resource_usage_tracker.license_purchases import (
    LicensePurchaseGet,
    LicensesPurchasesPage,
)
from models_library.basic_types import IDStr
from models_library.products import ProductName
from models_library.resource_tracker_license_purchases import (
    LicensePurchaseID,
    LicensePurchasesCreate,
)
from models_library.rest_ordering import OrderBy
from models_library.wallets import WalletID
from servicelib.rabbitmq import RPCRouter

from ...services import license_purchases

router = RPCRouter()


@router.expose(reraise_if_error_type=())
async def get_license_purchases_page(
    app: FastAPI,
    *,
    product_name: ProductName,
    wallet_id: WalletID,
    offset: int = 0,
    limit: int = 20,
    order_by: OrderBy = OrderBy(field=IDStr("purchased_at")),
) -> LicensesPurchasesPage:
    return await license_purchases.list_license_purchases(
        db_engine=app.state.engine,
        product_name=product_name,
        offset=offset,
        limit=limit,
        filter_wallet_id=wallet_id,
        order_by=order_by,
    )


@router.expose(reraise_if_error_type=())
async def get_license_purchase(
    app: FastAPI,
    *,
    product_name: ProductName,
    licensed_item_purchase_id: LicensePurchaseID,
) -> LicensePurchaseGet:
    return await license_purchases.get_license_purchase(
        db_engine=app.state.engine,
        product_name=product_name,
        licensed_item_purchase_id=licensed_item_purchase_id,
    )


@router.expose(reraise_if_error_type=())
async def create_license_purchase(
    app: FastAPI, *, data: LicensePurchasesCreate
) -> LicensePurchaseGet:
    return await license_purchases.create_license_purchase(
        rabbitmq_client=app.state.rabbitmq_client, db_engine=app.state.engine, data=data
    )
