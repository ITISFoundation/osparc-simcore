import logging
from typing import Literal, cast

from aiohttp import web
from models_library.licenses import (
    LicensedItem,
    LicensedItemDB,
    LicensedItemID,
    LicensedItemPatchDB,
    LicensedResourceType,
)
from models_library.products import ProductName
from models_library.resource_tracker import PricingPlanId
from models_library.rest_ordering import OrderBy, OrderDirection
from pydantic import NonNegativeInt
from simcore_postgres_database.models.licensed_item_to_resource import (
    licensed_item_to_resource,
)
from simcore_postgres_database.models.licensed_items import licensed_items
from simcore_postgres_database.models.licensed_resources import licensed_resources
from simcore_postgres_database.utils_repos import (
    get_columns_from_db_model,
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy import asc, desc, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql import select

from ..db.plugin import get_asyncpg_engine
from .errors import LicensedItemNotFoundError

_logger = logging.getLogger(__name__)


_SELECTION_ARGS = get_columns_from_db_model(licensed_items, LicensedItemDB)


def _create_insert_query(
    display_name: str,
    licensed_resource_type: LicensedResourceType,
    product_name: ProductName,
    pricing_plan_id: PricingPlanId,
):
    return (
        postgresql.insert(licensed_items)
        .values(
            licensed_resource_type=licensed_resource_type,
            display_name=display_name,
            pricing_plan_id=pricing_plan_id,
            product_name=product_name,
            created=func.now(),
            modified=func.now(),
        )
        .returning(*_SELECTION_ARGS)
    )


async def create(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    display_name: str,
    licensed_resource_type: LicensedResourceType,
    product_name: ProductName,
    pricing_plan_id: PricingPlanId,
) -> LicensedItemDB:

    query = _create_insert_query(
        display_name,
        licensed_resource_type,
        product_name,
        pricing_plan_id,
    )
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.execute(query)
        row = result.one()
        return LicensedItemDB.model_validate(row)


async def list_(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    product_name: ProductName,
    offset: NonNegativeInt,
    limit: NonNegativeInt,
    order_by: OrderBy,
    # filters
    trashed: Literal["exclude", "only", "include"] = "exclude",
    inactive: Literal["exclude", "only", "include"] = "exclude",
) -> tuple[int, list[LicensedItemDB]]:

    base_query = (
        select(*_SELECTION_ARGS)
        .select_from(licensed_items)
        .where(licensed_items.c.product_name == product_name)
    )

    # Apply trashed filter
    if trashed == "exclude":
        base_query = base_query.where(licensed_items.c.trashed.is_(None))
    elif trashed == "only":
        base_query = base_query.where(licensed_items.c.trashed.is_not(None))

    if inactive == "only":
        base_query = base_query.where(
            licensed_items.c.product_name.is_(None)
            | licensed_items.c.licensed_item_id.is_(None)
        )
    elif inactive == "exclude":
        base_query = base_query.where(
            licensed_items.c.product_name.is_not(None)
            & licensed_items.c.licensed_item_id.is_not(None)
        )

    # Select total count from base_query
    subquery = base_query.subquery()
    count_query = select(func.count()).select_from(subquery)

    # Ordering and pagination
    if order_by.direction == OrderDirection.ASC:
        list_query = base_query.order_by(asc(getattr(licensed_items.c, order_by.field)))
    else:
        list_query = base_query.order_by(
            desc(getattr(licensed_items.c, order_by.field))
        )
    list_query = list_query.offset(offset).limit(limit)

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        total_count = await conn.scalar(count_query)

        result = await conn.stream(list_query)
        items: list[LicensedItemDB] = [
            LicensedItemDB.model_validate(row) async for row in result
        ]

        return cast(int, total_count), items


async def get(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    licensed_item_id: LicensedItemID,
    product_name: ProductName,
) -> LicensedItemDB:
    select_query = (
        select(*_SELECTION_ARGS)
        .select_from(licensed_items)
        .where(
            (licensed_items.c.licensed_item_id == licensed_item_id)
            & (licensed_items.c.product_name == product_name)
        )
    )

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.execute(select_query)
        row = result.one_or_none()
        if row is None:
            raise LicensedItemNotFoundError(licensed_item_id=licensed_item_id)
        return LicensedItemDB.model_validate(row)


async def update(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    product_name: ProductName,
    licensed_item_id: LicensedItemID,
    updates: LicensedItemPatchDB,
) -> LicensedItemDB:
    # NOTE: at least 'touch' if updated_values is empty
    _updates = {
        **updates.model_dump(exclude_unset=True),
        licensed_items.c.modified.name: func.now(),
    }

    # trashing
    assert "trash" in dict(LicensedItemPatchDB.model_fields)  # nosec
    if trash := _updates.pop("trash", None):
        _updates[licensed_items.c.trashed.name] = func.now() if trash else None

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.execute(
            licensed_items.update()
            .values(**_updates)
            .where(
                (licensed_items.c.licensed_item_id == licensed_item_id)
                & (licensed_items.c.product_name == product_name)
            )
            .returning(*_SELECTION_ARGS)
        )
        row = result.one_or_none()
        if row is None:
            raise LicensedItemNotFoundError(licensed_item_id=licensed_item_id)
        return LicensedItemDB.model_validate(row)


async def delete(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    licensed_item_id: LicensedItemID,
    product_name: ProductName,
) -> None:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        await conn.execute(
            licensed_items.delete().where(
                (licensed_items.c.licensed_item_id == licensed_item_id)
                & (licensed_items.c.product_name == product_name)
            )
        )


### LICENSED ITEMS DOMAIN


_SELECTION_LICENSED_ITEM_ARGS = (
    licensed_items.c.licensed_item_id,
    licensed_items.c.display_name,
    licensed_items.c.licensed_resource_type,
    licensed_resources.c.licensed_resource_data,
    licensed_items.c.pricing_plan_id,
    licensed_items.c.created,
    licensed_items.c.modified,
)


async def get_licensed_item(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    licensed_item_id: LicensedItemID,
    product_name: ProductName,
    filter_by_license_resource_type: LicensedResourceType | None = None,
) -> LicensedItem:

    licensed_resource_subquery = (
        select(
            licensed_resources.c.licensed_resource_id,
            func.jsonb_object_agg(
                workspaces_access_rights.c.gid,
                func.jsonb_build_object(
                    "read",
                    workspaces_access_rights.c.read,
                    "write",
                    workspaces_access_rights.c.write,
                    "delete",
                    workspaces_access_rights.c.delete,
                ),
            ).label("access_rights"),
        ).group_by(licensed_resources.c.licensed_resource_id)
    ).subquery("licensed_resource_subquery")

    select_query = (
        select(*_SELECTION_LICENSED_ITEM_ARGS)
        .select_from(
            licensed_items.join(
                licensed_item_to_resource,
                licensed_items.c.licensed_item_id
                == licensed_item_to_resource.c.licensed_item_id,
            ).join(
                licensed_resource_subquery,
                licensed_item_to_resource.c.licensed_resource_id
                == licensed_resource_subquery.c.licensed_resource_id,
            )
        )
        .where(
            (licensed_items.c.licensed_item_id == licensed_item_id)
            & (licensed_items.c.product_name == product_name)
        )
    )

    if filter_by_license_resource_type:
        select_query = select_query.where(
            licensed_items.c.licensed_resource_type == filter_by_license_resource_type
        )

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.execute(select_query)
        row = result.one_or_none()
        if row is None:
            raise LicensedItemNotFoundError(licensed_item_id=licensed_item_id)
        return LicensedItem.model_validate(row)
