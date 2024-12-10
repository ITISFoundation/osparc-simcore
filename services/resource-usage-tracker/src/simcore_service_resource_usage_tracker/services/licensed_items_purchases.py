from typing import Annotated

from fastapi import Depends
from models_library.api_schemas_resource_usage_tracker.licensed_items_purchases import (
    LicensedItemPurchaseGet,
    LicensedItemsPurchasesPage,
)
from models_library.products import ProductName
from models_library.resource_tracker_licensed_items_purchases import (
    LicensedItemPurchaseID,
    LicensedItemsPurchasesCreate,
)
from models_library.rest_ordering import OrderBy
from models_library.wallets import WalletID
from sqlalchemy.ext.asyncio import AsyncEngine

from ..api.rest.dependencies import get_resource_tracker_db_engine
from ..models.licensed_items_purchases import (
    CreateLicensedItemsPurchasesDB,
    LicensedItemsPurchasesDB,
)
from .modules.db import licensed_items_purchases_db


async def list_licensed_items_purchases(
    db_engine: Annotated[AsyncEngine, Depends(get_resource_tracker_db_engine)],
    *,
    product_name: ProductName,
    filter_wallet_id: WalletID,
    offset: int = 0,
    limit: int = 20,
    order_by: OrderBy,
) -> LicensedItemsPurchasesPage:
    total, licensed_items_purchases_list_db = await licensed_items_purchases_db.list_(
        db_engine,
        product_name=product_name,
        filter_wallet_id=filter_wallet_id,
        offset=offset,
        limit=limit,
        order_by=order_by,
    )
    return LicensedItemsPurchasesPage(
        total=total,
        items=[
            LicensedItemPurchaseGet(
                licensed_item_purchase_id=licensed_item_purchase_db.licensed_item_purchase_id,
                product_name=licensed_item_purchase_db.product_name,
                licensed_item_id=licensed_item_purchase_db.licensed_item_id,
                wallet_id=licensed_item_purchase_db.wallet_id,
                wallet_name=licensed_item_purchase_db.wallet_name,
                pricing_unit_cost_id=licensed_item_purchase_db.pricing_unit_cost_id,
                pricing_unit_cost=licensed_item_purchase_db.pricing_unit_cost,
                start_at=licensed_item_purchase_db.start_at,
                expire_at=licensed_item_purchase_db.expire_at,
                num_of_seats=licensed_item_purchase_db.num_of_seats,
                purchased_by_user=licensed_item_purchase_db.purchased_by_user,
                purchased_at=licensed_item_purchase_db.purchased_at,
                modified=licensed_item_purchase_db.modified,
            )
            for licensed_item_purchase_db in licensed_items_purchases_list_db
        ],
    )


async def get_licensed_item_purchase(
    db_engine: Annotated[AsyncEngine, Depends(get_resource_tracker_db_engine)],
    *,
    product_name: ProductName,
    licensed_item_purchase_id: LicensedItemPurchaseID,
) -> LicensedItemPurchaseGet:
    licensed_item_purchase_db: LicensedItemsPurchasesDB = (
        await licensed_items_purchases_db.get(
            db_engine,
            product_name=product_name,
            licensed_item_purchase_id=licensed_item_purchase_id,
        )
    )

    return LicensedItemPurchaseGet(
        licensed_item_purchase_id=licensed_item_purchase_db.licensed_item_purchase_id,
        product_name=licensed_item_purchase_db.product_name,
        licensed_item_id=licensed_item_purchase_db.licensed_item_id,
        wallet_id=licensed_item_purchase_db.wallet_id,
        wallet_name=licensed_item_purchase_db.wallet_name,
        pricing_unit_cost_id=licensed_item_purchase_db.pricing_unit_cost_id,
        pricing_unit_cost=licensed_item_purchase_db.pricing_unit_cost,
        start_at=licensed_item_purchase_db.start_at,
        expire_at=licensed_item_purchase_db.expire_at,
        num_of_seats=licensed_item_purchase_db.num_of_seats,
        purchased_by_user=licensed_item_purchase_db.purchased_by_user,
        purchased_at=licensed_item_purchase_db.purchased_at,
        modified=licensed_item_purchase_db.modified,
    )


async def create_licensed_item_purchase(
    db_engine: Annotated[AsyncEngine, Depends(get_resource_tracker_db_engine)],
    *,
    data: LicensedItemsPurchasesCreate,
) -> LicensedItemPurchaseGet:

    _create_db_data = CreateLicensedItemsPurchasesDB(
        product_name=data.product_name,
        licensed_item_id=data.licensed_item_id,
        wallet_id=data.wallet_id,
        wallet_name=data.wallet_name,
        pricing_unit_cost_id=data.pricing_unit_cost_id,
        pricing_unit_cost=data.pricing_unit_cost,
        start_at=data.start_at,
        expire_at=data.expire_at,
        num_of_seats=data.num_of_seats,
        purchased_by_user=data.purchased_by_user,
        purchased_at=data.purchased_at,
    )

    licensed_item_purchase_db: LicensedItemsPurchasesDB = (
        await licensed_items_purchases_db.create(db_engine, data=_create_db_data)
    )

    return LicensedItemPurchaseGet(
        licensed_item_purchase_id=licensed_item_purchase_db.licensed_item_purchase_id,
        product_name=licensed_item_purchase_db.product_name,
        licensed_item_id=licensed_item_purchase_db.licensed_item_id,
        wallet_id=licensed_item_purchase_db.wallet_id,
        wallet_name=licensed_item_purchase_db.wallet_name,
        pricing_unit_cost_id=licensed_item_purchase_db.pricing_unit_cost_id,
        pricing_unit_cost=licensed_item_purchase_db.pricing_unit_cost,
        start_at=licensed_item_purchase_db.start_at,
        expire_at=licensed_item_purchase_db.expire_at,
        num_of_seats=licensed_item_purchase_db.num_of_seats,
        purchased_by_user=licensed_item_purchase_db.purchased_by_user,
        purchased_at=licensed_item_purchase_db.purchased_at,
        modified=licensed_item_purchase_db.modified,
    )
