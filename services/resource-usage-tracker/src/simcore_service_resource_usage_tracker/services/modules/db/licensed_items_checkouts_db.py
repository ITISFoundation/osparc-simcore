from datetime import datetime
from typing import cast

import sqlalchemy as sa
from models_library.licensed_items import LicensedItemID
from models_library.products import ProductName
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.wallets import WalletID
from pydantic import NonNegativeInt
from simcore_postgres_database.models.resource_tracker_licensed_items_checkouts import (
    resource_tracker_licensed_items_checkouts,
)
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from simcore_service_resource_usage_tracker.services.licensed_items_checkouts import (
    LicensedItemCheckoutID,
)
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from ....exceptions.errors import LicensedItemCheckoutNotFoundError
from ....models.licensed_items_checkouts import (
    CreateLicensedItemCheckoutDB,
    LicensedItemCheckoutDB,
)

_SELECTION_ARGS = (
    resource_tracker_licensed_items_checkouts.c.licensed_item_checkout_id,
    resource_tracker_licensed_items_checkouts.c.licensed_item_id,
    resource_tracker_licensed_items_checkouts.c.wallet_id,
    resource_tracker_licensed_items_checkouts.c.user_id,
    resource_tracker_licensed_items_checkouts.c.user_email,
    resource_tracker_licensed_items_checkouts.c.product_name,
    resource_tracker_licensed_items_checkouts.c.service_run_id,
    resource_tracker_licensed_items_checkouts.c.started_at,
    resource_tracker_licensed_items_checkouts.c.stopped_at,
    resource_tracker_licensed_items_checkouts.c.num_of_seats,
    resource_tracker_licensed_items_checkouts.c.modified,
)

assert set(LicensedItemCheckoutDB.model_fields) == {
    c.name for c in _SELECTION_ARGS
}  # nosec


async def create(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    data: CreateLicensedItemCheckoutDB,
) -> LicensedItemCheckoutDB:
    async with transaction_context(engine, connection) as conn:
        result = await conn.execute(
            resource_tracker_licensed_items_checkouts.insert()
            .values(
                licensed_item_id=data.licensed_item_id,
                wallet_id=data.wallet_id,
                user_id=data.user_id,
                user_email=data.user_email,
                product_name=data.product_name,
                service_run_id=data.service_run_id,
                started_at=data.started_at,
                stopped_at=None,
                num_of_seats=data.num_of_seats,
                modified=sa.func.now(),
            )
            .returning(*_SELECTION_ARGS)
        )
        row = result.first()
        return LicensedItemCheckoutDB.model_validate(row)


async def list_(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    product_name: ProductName,
    filter_wallet_id: WalletID,
    offset: NonNegativeInt,
    limit: NonNegativeInt,
    order_by: OrderBy,
) -> tuple[int, list[LicensedItemCheckoutDB]]:
    base_query = (
        sa.select(*_SELECTION_ARGS)
        .select_from(resource_tracker_licensed_items_checkouts)
        .where(
            (resource_tracker_licensed_items_checkouts.c.product_name == product_name)
            & (
                resource_tracker_licensed_items_checkouts.c.wallet_id
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
            sa.asc(getattr(resource_tracker_licensed_items_checkouts.c, order_by.field))
        )
    else:
        list_query = base_query.order_by(
            sa.desc(
                getattr(resource_tracker_licensed_items_checkouts.c, order_by.field)
            )
        )
    list_query = list_query.offset(offset).limit(limit)

    async with pass_or_acquire_connection(engine, connection) as conn:
        total_count = await conn.scalar(count_query)

        result = await conn.stream(list_query)
        items: list[LicensedItemCheckoutDB] = [
            LicensedItemCheckoutDB.model_validate(row) async for row in result
        ]

        return cast(int, total_count), items


async def get(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    licensed_item_checkout_id: LicensedItemCheckoutID,
    product_name: ProductName,
) -> LicensedItemCheckoutDB:
    base_query = (
        sa.select(*_SELECTION_ARGS)
        .select_from(resource_tracker_licensed_items_checkouts)
        .where(
            (
                resource_tracker_licensed_items_checkouts.c.licensed_item_checkout_id
                == licensed_item_checkout_id
            )
            & (resource_tracker_licensed_items_checkouts.c.product_name == product_name)
        )
    )

    async with pass_or_acquire_connection(engine, connection) as conn:
        result = await conn.stream(base_query)
        row = await result.first()
        if row is None:
            raise LicensedItemCheckoutNotFoundError(
                licensed_item_checkout_id=licensed_item_checkout_id
            )
        return LicensedItemCheckoutDB.model_validate(row)


async def update(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    licensed_item_checkout_id: LicensedItemCheckoutID,
    product_name: ProductName,
    stopped_at: datetime,
) -> LicensedItemCheckoutDB:
    update_stmt = (
        resource_tracker_licensed_items_checkouts.update()
        .values(
            modified=sa.func.now(),
            stopped_at=stopped_at,
        )
        .where(
            (
                resource_tracker_licensed_items_checkouts.c.licensed_item_checkout_id
                == licensed_item_checkout_id
            )
            & (resource_tracker_licensed_items_checkouts.c.product_name == product_name)
            & (resource_tracker_licensed_items_checkouts.c.stopped_at.is_(None))
        )
        .returning(sa.literal_column("*"))
    )

    async with transaction_context(engine, connection) as conn:
        result = await conn.execute(update_stmt)
        row = result.first()
        if row is None:
            raise LicensedItemCheckoutNotFoundError(
                licensed_item_checkout_id=licensed_item_checkout_id
            )
        return LicensedItemCheckoutDB.model_validate(row)


async def get_currently_used_seats_for_item_and_wallet(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    licensed_item_id: LicensedItemID,
    wallet_id: WalletID,
    product_name: ProductName,
) -> int:
    sum_stmt = sa.select(
        sa.func.sum(resource_tracker_licensed_items_checkouts.c.num_of_seats)
    ).where(
        (resource_tracker_licensed_items_checkouts.c.wallet_id == wallet_id)
        & (
            resource_tracker_licensed_items_checkouts.c.licensed_item_id
            == licensed_item_id
        )
        & (resource_tracker_licensed_items_checkouts.c.product_name == product_name)
        & (resource_tracker_licensed_items_checkouts.c.stopped_at.is_(None))
    )

    async with pass_or_acquire_connection(engine, connection) as conn:
        result = await conn.execute(sum_stmt)
        row = result.first()
        if row is None or row[0] is None:
            return 0
        return row[0]
