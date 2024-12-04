""" Database API

    - Adds a layer to the postgres API with a focus on the projects comments

"""

import logging
from typing import cast

from aiohttp import web
from models_library.license_goods import (
    LicenseGoodDB,
    LicenseGoodID,
    LicenseGoodUpdateDB,
    LicenseResourceType,
)
from models_library.products import ProductName
from models_library.resource_tracker import PricingPlanId
from models_library.rest_ordering import OrderBy, OrderDirection
from pydantic import NonNegativeInt
from simcore_postgres_database.models.license_goods import license_goods
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy import asc, desc, func
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql import select

from ..db.plugin import get_asyncpg_engine
from .errors import LicenseGoodNotFoundError

_logger = logging.getLogger(__name__)


_SELECTION_ARGS = (
    license_goods.c.license_good_id,
    license_goods.c.name,
    license_goods.c.license_resource_type,
    license_goods.c.pricing_plan_id,
    license_goods.c.product_name,
    license_goods.c.created,
    license_goods.c.modified,
)

assert set(LicenseGoodDB.model_fields) == {c.name for c in _SELECTION_ARGS}  # nosec


async def create(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    product_name: ProductName,
    name: str,
    license_resource_type: LicenseResourceType,
    pricing_plan_id: PricingPlanId,
) -> LicenseGoodDB:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(
            license_goods.insert()
            .values(
                name=name,
                license_resource_type=license_resource_type,
                pricing_plan_id=pricing_plan_id,
                product_name=product_name,
                created=func.now(),
                modified=func.now(),
            )
            .returning(*_SELECTION_ARGS)
        )
        row = await result.first()
        return LicenseGoodDB.model_validate(row)


async def list_(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    product_name: ProductName,
    offset: NonNegativeInt,
    limit: NonNegativeInt,
    order_by: OrderBy,
) -> tuple[int, list[LicenseGoodDB]]:
    base_query = (
        select(*_SELECTION_ARGS)
        .select_from(license_goods)
        .where(license_goods.c.product_name == product_name)
    )

    # Select total count from base_query
    subquery = base_query.subquery()
    count_query = select(func.count()).select_from(subquery)

    # Ordering and pagination
    if order_by.direction == OrderDirection.ASC:
        list_query = base_query.order_by(asc(getattr(license_goods.c, order_by.field)))
    else:
        list_query = base_query.order_by(desc(getattr(license_goods.c, order_by.field)))
    list_query = list_query.offset(offset).limit(limit)

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        total_count = await conn.scalar(count_query)

        result = await conn.stream(list_query)
        items: list[LicenseGoodDB] = [
            LicenseGoodDB.model_validate(row) async for row in result
        ]

        return cast(int, total_count), items


async def get(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    license_good_id: LicenseGoodID,
    product_name: ProductName,
) -> LicenseGoodDB:
    base_query = (
        select(*_SELECTION_ARGS)
        .select_from(license_goods)
        .where(
            (license_goods.c.license_good_id == license_good_id)
            & (license_goods.c.product_name == product_name)
        )
    )

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(base_query)
        row = await result.first()
        if row is None:
            raise LicenseGoodNotFoundError(license_good_id=license_good_id)
        return LicenseGoodDB.model_validate(row)


async def update(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    product_name: ProductName,
    license_good_id: LicenseGoodID,
    updates: LicenseGoodUpdateDB,
) -> LicenseGoodDB:
    # NOTE: at least 'touch' if updated_values is empty
    _updates = {
        **updates.dict(exclude_unset=True),
        "modified": func.now(),
    }

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(
            license_goods.update()
            .values(**_updates)
            .where(
                (license_goods.c.license_good_id == license_good_id)
                & (license_goods.c.product_name == product_name)
            )
            .returning(*_SELECTION_ARGS)
        )
        row = await result.first()
        if row is None:
            raise LicenseGoodNotFoundError(license_good_id=license_good_id)
        return LicenseGoodDB.model_validate(row)


async def delete(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    license_good_id: LicenseGoodID,
    product_name: ProductName,
) -> None:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        await conn.execute(
            license_goods.delete().where(
                (license_goods.c.license_good_id == license_good_id)
                & (license_goods.c.product_name == product_name)
            )
        )
