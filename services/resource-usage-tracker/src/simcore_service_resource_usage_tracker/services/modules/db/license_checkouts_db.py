import logging
from datetime import datetime
from typing import cast

import sqlalchemy as sa
from models_library.licenses import LicenseID
from models_library.products import ProductName
from models_library.resource_tracker_license_checkouts import LicenseCheckoutID
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.services_types import ServiceRunID
from models_library.wallets import WalletID
from pydantic import NonNegativeInt
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker.errors import (
    LicenseCheckoutNotFoundError,
)
from simcore_postgres_database.models.resource_tracker_license_checkouts import (
    resource_tracker_license_checkouts,
)
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from ....models.license_checkouts import CreateLicenseCheckoutDB, LicenseCheckoutDB

_logger = logging.getLogger(__name__)


_SELECTION_ARGS = (
    resource_tracker_license_checkouts.c.license_checkout_id,
    resource_tracker_license_checkouts.c.license_id,
    resource_tracker_license_checkouts.c.wallet_id,
    resource_tracker_license_checkouts.c.user_id,
    resource_tracker_license_checkouts.c.user_email,
    resource_tracker_license_checkouts.c.product_name,
    resource_tracker_license_checkouts.c.service_run_id,
    resource_tracker_license_checkouts.c.started_at,
    resource_tracker_license_checkouts.c.stopped_at,
    resource_tracker_license_checkouts.c.num_of_seats,
    resource_tracker_license_checkouts.c.modified,
)

assert set(LicenseCheckoutDB.model_fields) == {c.name for c in _SELECTION_ARGS}  # nosec


async def create(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    data: CreateLicenseCheckoutDB,
) -> LicenseCheckoutDB:
    async with transaction_context(engine, connection) as conn:
        result = await conn.execute(
            resource_tracker_license_checkouts.insert()
            .values(
                license_id=data.license_id,
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
        return LicenseCheckoutDB.model_validate(row)


async def list_(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    product_name: ProductName,
    filter_wallet_id: WalletID,
    offset: NonNegativeInt,
    limit: NonNegativeInt,
    order_by: OrderBy,
) -> tuple[int, list[LicenseCheckoutDB]]:
    base_query = (
        sa.select(*_SELECTION_ARGS)
        .select_from(resource_tracker_license_checkouts)
        .where(
            (resource_tracker_license_checkouts.c.product_name == product_name)
            & (resource_tracker_license_checkouts.c.wallet_id == filter_wallet_id)
        )
    )

    # Select total count from base_query
    subquery = base_query.subquery()
    count_query = sa.select(sa.func.count()).select_from(subquery)

    # Ordering and pagination
    if order_by.direction == OrderDirection.ASC:
        list_query = base_query.order_by(
            sa.asc(getattr(resource_tracker_license_checkouts.c, order_by.field))
        )
    else:
        list_query = base_query.order_by(
            sa.desc(getattr(resource_tracker_license_checkouts.c, order_by.field))
        )
    list_query = list_query.offset(offset).limit(limit)

    async with pass_or_acquire_connection(engine, connection) as conn:
        total_count = await conn.scalar(count_query)
        if total_count is None:
            total_count = 0

        result = await conn.stream(list_query)
        items: list[LicenseCheckoutDB] = [
            LicenseCheckoutDB.model_validate(row) async for row in result
        ]

        return cast(int, total_count), items


async def get(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    license_checkout_id: LicenseCheckoutID,
    product_name: ProductName,
) -> LicenseCheckoutDB:
    base_query = (
        sa.select(*_SELECTION_ARGS)
        .select_from(resource_tracker_license_checkouts)
        .where(
            (
                resource_tracker_license_checkouts.c.license_checkout_id
                == license_checkout_id
            )
            & (resource_tracker_license_checkouts.c.product_name == product_name)
        )
    )

    async with pass_or_acquire_connection(engine, connection) as conn:
        result = await conn.stream(base_query)
        row = await result.first()
        if row is None:
            raise LicenseCheckoutNotFoundError(license_checkout_id=license_checkout_id)
        return LicenseCheckoutDB.model_validate(row)


async def update(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    license_checkout_id: LicenseCheckoutID,
    product_name: ProductName,
    stopped_at: datetime,
) -> LicenseCheckoutDB:
    update_stmt = (
        resource_tracker_license_checkouts.update()
        .values(
            modified=sa.func.now(),
            stopped_at=stopped_at,
        )
        .where(
            (
                resource_tracker_license_checkouts.c.license_checkout_id
                == license_checkout_id
            )
            & (resource_tracker_license_checkouts.c.product_name == product_name)
            & (resource_tracker_license_checkouts.c.stopped_at.is_(None))
        )
        .returning(sa.literal_column("*"))
    )

    async with transaction_context(engine, connection) as conn:
        result = await conn.execute(update_stmt)
        row = result.first()
        if row is None:
            raise LicenseCheckoutNotFoundError(license_checkout_id=license_checkout_id)
        return LicenseCheckoutDB.model_validate(row)


async def get_currently_used_seats_for_item_and_wallet(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    license_id: LicenseID,
    wallet_id: WalletID,
    product_name: ProductName,
) -> int:
    sum_stmt = sa.select(
        sa.func.sum(resource_tracker_license_checkouts.c.num_of_seats)
    ).where(
        (resource_tracker_license_checkouts.c.wallet_id == wallet_id)
        & (resource_tracker_license_checkouts.c.license_id == license_id)
        & (resource_tracker_license_checkouts.c.product_name == product_name)
        & (resource_tracker_license_checkouts.c.stopped_at.is_(None))
    )

    async with pass_or_acquire_connection(engine, connection) as conn:
        total_sum = await conn.scalar(sum_stmt)
        if total_sum is None:
            return 0
        return cast(int, total_sum)


async def force_release_license_seats_by_run_id(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    service_run_id: ServiceRunID,
) -> None:
    """
    Purpose: This function is utilized by a periodic heartbeat check task that monitors whether running services are
    sending heartbeat signals. If heartbeat signals are not received within a specified timeframe and a service is
    deemed unhealthy, this function ensures the proper release of any licensed seats that were not correctly released by
    the unhealthy service.
    Currently, this functionality is primarily used to handle the release of a single seat allocated to the VIP model.
    """
    update_stmt = (
        resource_tracker_license_checkouts.update()
        .values(
            modified=sa.func.now(),
            stopped_at=sa.func.now(),
        )
        .where(
            (resource_tracker_license_checkouts.c.service_run_id == service_run_id)
            & (resource_tracker_license_checkouts.c.stopped_at.is_(None))
        )
        .returning(sa.literal_column("*"))
    )

    async with transaction_context(engine, connection) as conn:
        result = await conn.execute(update_stmt)
        released_seats = result.fetchall()
        if released_seats:
            _logger.error(
                "Force release of %s seats: %s", len(released_seats), released_seats
            )
