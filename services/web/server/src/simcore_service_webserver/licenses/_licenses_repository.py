""" Database API

    - Adds a layer to the postgres API with a focus on the projects comments

"""

import logging
from typing import cast

from aiohttp import web
from models_library.licensed_items import LicensedItemID, LicensedResourceType
from models_library.licenses import License, LicenseDB, LicenseID, LicenseUpdateDB
from models_library.products import ProductName
from models_library.resource_tracker import PricingPlanId
from models_library.rest_ordering import OrderBy, OrderDirection
from pydantic import NonNegativeInt
from simcore_postgres_database.models.license_to_resource import license_to_resource
from simcore_postgres_database.models.licensed_items import licensed_resources
from simcore_postgres_database.models.licenses import licenses
from simcore_postgres_database.utils_repos import (
    get_columns_from_db_model,
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy import asc, desc, func
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql import select

from ..db.plugin import get_asyncpg_engine
from .errors import LicenseNotFoundError

_logger = logging.getLogger(__name__)


_SELECTION_ARGS = get_columns_from_db_model(licenses, LicenseDB)


async def create(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    display_name: str,
    licensed_resource_type: LicensedResourceType,
    product_name: ProductName,
    pricing_plan_id: PricingPlanId,
) -> LicenseDB:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.execute(
            licenses.insert()
            .values(
                product_name=product_name,
                display_name=display_name,
                licensed_resource_type=licensed_resource_type,
                pricing_plan_id=pricing_plan_id,
                created=func.now(),
                modified=func.now(),
            )
            .returning(*_SELECTION_ARGS)
        )
        row = result.one()
        return LicenseDB.model_validate(row)


async def list_(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    product_name: ProductName,
    offset: NonNegativeInt,
    limit: NonNegativeInt,
    order_by: OrderBy,
) -> tuple[int, list[LicenseDB]]:

    base_query = (
        select(*_SELECTION_ARGS)
        .select_from(licenses)
        .where(licenses.c.product_name == product_name)
    )

    # Select total count from base_query
    subquery = base_query.subquery()
    count_query = select(func.count()).select_from(subquery)

    # Ordering and pagination
    if order_by.direction == OrderDirection.ASC:
        list_query = base_query.order_by(asc(getattr(licenses.c, order_by.field)))
    else:
        list_query = base_query.order_by(desc(getattr(licenses.c, order_by.field)))
    list_query = list_query.offset(offset).limit(limit)

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        total_count = await conn.scalar(count_query)

        result = await conn.stream(list_query)
        items: list[LicenseDB] = [LicenseDB.model_validate(row) async for row in result]

        return cast(int, total_count), items


async def get(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    license_id: LicenseID,
    product_name: ProductName,
) -> LicenseDB:
    base_query = (
        select(*_SELECTION_ARGS)
        .select_from(licenses)
        .where(
            (licenses.c.license_id == license_id)
            & (licenses.c.product_name == product_name)
        )
    )

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(base_query)
        row = await result.first()
        if row is None:
            raise LicenseNotFoundError(license_id=license_id)
        return LicenseDB.model_validate(row)


async def update(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    product_name: ProductName,
    license_id: LicenseID,
    updates: LicenseUpdateDB,
) -> LicenseDB:
    # NOTE: at least 'touch' if updated_values is empty
    _updates = {
        **updates.model_dump(exclude_unset=True),
        licenses.c.modified.name: func.now(),
    }
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.execute(
            licenses.update()
            .values(**_updates)
            .where(
                (licenses.c.license_id == license_id)
                & (licenses.c.product_name == product_name)
            )
            .returning(*_SELECTION_ARGS)
        )
        row = result.one_or_none()
        if row is None:
            raise LicenseNotFoundError(license_id=license_id)
        return LicenseDB.model_validate(row)


async def delete(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    license_id: LicenseID,
    product_name: ProductName,
) -> None:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        await conn.execute(
            licenses.delete().where(
                (licenses.c.license_id == license_id)
                & (licenses.c.product_name == product_name)
            )
        )


#### DOMAIN MODEL


async def list_licenses(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    product_name: ProductName,
    offset: NonNegativeInt,
    limit: NonNegativeInt,
    order_by: OrderBy,
) -> tuple[int, list[License]]:

    licensed_resources_subquery = (
        select(
            license_to_resource.c.license_id,
            func.jsonb_agg(licensed_resources.c.licensed_resource_data).label(
                "resources"
            ),
        )
        .select_from(
            license_to_resource.join(
                licensed_resources,
                license_to_resource.c.licensed_item_id
                == licensed_resources.c.licensed_item_id,
            )
        )
        .group_by(license_to_resource.c.license_id)
    ).subquery("licensed_resources_subquery")

    base_query = (
        select(
            *_SELECTION_ARGS,
            licensed_resources_subquery.c.resources,
        )
        .select_from(
            licenses.join(
                licensed_resources_subquery,
                licenses.c.license_id == licensed_resources_subquery.c.license_id,
            )
        )
        .where(licenses.c.product_name == product_name)
    )

    # Select total count from base_query
    subquery = base_query.subquery()
    count_query = select(func.count()).select_from(subquery)

    # Ordering and pagination
    if order_by.direction == OrderDirection.ASC:
        list_query = base_query.order_by(asc(getattr(licenses.c, order_by.field)))
    else:
        list_query = base_query.order_by(desc(getattr(licenses.c, order_by.field)))
    list_query = list_query.offset(offset).limit(limit)

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        total_count = await conn.scalar(count_query)

        result = await conn.stream(list_query)
        items: list[License] = [License.model_validate(row) async for row in result]

        return cast(int, total_count), items


async def get_license(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    license_id: LicenseID,
    product_name: ProductName,
) -> License:
    licensed_resources_subquery = (
        select(
            license_to_resource.c.license_id,
            func.jsonb_agg(licensed_resources.c.licensed_resource_data).label(
                "resources"
            ),
        )
        .select_from(
            license_to_resource.join(
                licensed_resources,
                license_to_resource.c.licensed_item_id
                == licensed_resources.c.licensed_item_id,
            )
        )
        .where(license_to_resource.c.license_id == license_id)
        .group_by(license_to_resource.c.license_id)
    ).subquery("licensed_resources_subquery")

    base_query = (
        select(
            *_SELECTION_ARGS,
            licensed_resources_subquery.c.resources,
        )
        .select_from(
            licenses.join(
                licensed_resources_subquery,
                licenses.c.license_id == licensed_resources_subquery.c.license_id,
            )
        )
        .where(
            (licenses.c.product_name == product_name)
            & (licenses.c.license_id == license_id)
        )
    )

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(base_query)
        row = await result.first()
        if row is None:
            raise LicenseNotFoundError(license_id=license_id)
        return License.model_validate(row)


### License to Resource


async def add_licensed_resource_to_license(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    licensed_item_id: LicensedItemID,
    license_id: LicenseID,
) -> None:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        await conn.execute(
            license_to_resource.insert().values(
                license_id=license_id,
                licensed_item_id=licensed_item_id,
                created=func.now(),
                modified=func.now(),
            )
        )


async def delete_licensed_resource_from_license(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    licensed_item_id: LicensedItemID,
    license_id: LicenseID,
) -> None:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        await conn.execute(
            license_to_resource.delete().where(
                (license_to_resource.c.license_id == license_id)
                & (license_to_resource.c.licensed_item_id == licensed_item_id)
            )
        )
