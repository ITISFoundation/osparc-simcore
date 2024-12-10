from typing import cast

import sqlalchemy as sa
from models_library.products import ProductName
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.wallets import WalletID
from pydantic import NonNegativeInt
from simcore_postgres_database.models.resource_tracker_licensed_items_purchases import (
    resource_tracker_licensed_items_purchases,
)
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from ....exceptions.errors import LicensedItemPurchaseNotFoundError
from ....models.licensed_items_purchases import (
    CreateLicensedItemsPurchasesDB,
    LicensedItemPurchaseID,
    LicensedItemsPurchasesDB,
)

_SELECTION_ARGS = (
    resource_tracker_licensed_items_purchases.c.licensed_item_purchase_id,
    resource_tracker_licensed_items_purchases.c.product_name,
    resource_tracker_licensed_items_purchases.c.licensed_item_id,
    resource_tracker_licensed_items_purchases.c.wallet_id,
    resource_tracker_licensed_items_purchases.c.wallet_name,
    resource_tracker_licensed_items_purchases.c.pricing_unit_cost_id,
    resource_tracker_licensed_items_purchases.c.pricing_unit_cost,
    resource_tracker_licensed_items_purchases.c.start_at,
    resource_tracker_licensed_items_purchases.c.expire_at,
    resource_tracker_licensed_items_purchases.c.num_of_seats,
    resource_tracker_licensed_items_purchases.c.purchased_by_user,
    resource_tracker_licensed_items_purchases.c.purchased_at,
    resource_tracker_licensed_items_purchases.c.modified,
)

assert set(LicensedItemsPurchasesDB.model_fields) == {
    c.name for c in _SELECTION_ARGS
}  # nosec


async def create(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    data: CreateLicensedItemsPurchasesDB,
) -> LicensedItemsPurchasesDB:
    async with transaction_context(engine, connection) as conn:
        result = await conn.stream(
            resource_tracker_licensed_items_purchases.insert()
            .values(
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
                modified=sa.func.now(),
            )
            .returning(*_SELECTION_ARGS)
        )
        row = await result.first()
        return LicensedItemsPurchasesDB.model_validate(row)


async def list_(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    product_name: ProductName,
    filter_wallet_id: WalletID,
    offset: NonNegativeInt,
    limit: NonNegativeInt,
    order_by: OrderBy,
) -> tuple[int, list[LicensedItemsPurchasesDB]]:
    base_query = (
        sa.select(*_SELECTION_ARGS)
        .select_from(resource_tracker_licensed_items_purchases)
        .where(
            (resource_tracker_licensed_items_purchases.c.product_name == product_name)
            & (
                resource_tracker_licensed_items_purchases.c.wallet_id
                == filter_wallet_id
            )
        )
    )

    # Select total count from base_query
    subquery = base_query.subquery()
    count_query = sa.select(sa.func.count()).select_from(subquery)

    # Ordering and pagination
    if order_by.direction == OrderDirection.ASC:
        list_query = base_query.order_by(
            sa.asc(getattr(resource_tracker_licensed_items_purchases.c, order_by.field))
        )
    else:
        list_query = base_query.order_by(
            sa.desc(
                getattr(resource_tracker_licensed_items_purchases.c, order_by.field)
            )
        )
    list_query = list_query.offset(offset).limit(limit)

    async with pass_or_acquire_connection(engine, connection) as conn:
        total_count = await conn.scalar(count_query)

        result = await conn.stream(list_query)
        items: list[LicensedItemsPurchasesDB] = [
            LicensedItemsPurchasesDB.model_validate(row) async for row in result
        ]

        return cast(int, total_count), items


async def get(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    licensed_item_purchase_id: LicensedItemPurchaseID,
    product_name: ProductName,
) -> LicensedItemsPurchasesDB:
    base_query = (
        sa.select(*_SELECTION_ARGS)
        .select_from(resource_tracker_licensed_items_purchases)
        .where(
            (
                resource_tracker_licensed_items_purchases.c.licensed_item_purchase_id
                == licensed_item_purchase_id
            )
            & (resource_tracker_licensed_items_purchases.c.product_name == product_name)
        )
    )

    async with pass_or_acquire_connection(engine, connection) as conn:
        result = await conn.stream(base_query)
        row = await result.first()
        if row is None:
            raise LicensedItemPurchaseNotFoundError(
                licensed_item_purchase_id=licensed_item_purchase_id
            )
        return LicensedItemsPurchasesDB.model_validate(row)
