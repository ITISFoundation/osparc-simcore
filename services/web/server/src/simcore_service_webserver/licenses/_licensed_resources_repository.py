import logging
from typing import Any

from aiohttp import web
from models_library.licenses import LicensedResourceDB, LicensedResourceType
from simcore_postgres_database.models.licensed_resources import licensed_resources
from simcore_postgres_database.utils_repos import (
    get_columns_from_db_model,
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy import func
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql import select

from ..db.plugin import get_asyncpg_engine
from .errors import LicensedResourceNotFoundError

_logger = logging.getLogger(__name__)


_SELECTION_ARGS = get_columns_from_db_model(licensed_resources, LicensedResourceDB)


def _create_insert_query(
    display_name: str,
    licensed_resource_name: str,
    licensed_resource_type: LicensedResourceType,
    licensed_resource_data: dict[str, Any] | None,
):
    return (
        postgresql.insert(licensed_resources)
        .values(
            licensed_resource_name=licensed_resource_name,
            licensed_resource_type=licensed_resource_type,
            licensed_resource_data=licensed_resource_data,
            display_name=display_name,
            created=func.now(),
            modified=func.now(),
        )
        .returning(*_SELECTION_ARGS)
    )


async def create_if_not_exists(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    display_name: str,
    licensed_resource_name: str,
    licensed_resource_type: LicensedResourceType,
    licensed_resource_data: dict[str, Any] | None = None,
) -> LicensedResourceDB:

    insert_or_none_query = _create_insert_query(
        display_name,
        licensed_resource_name,
        licensed_resource_type,
        licensed_resource_data,
    ).on_conflict_do_nothing()

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.execute(insert_or_none_query)
        row = result.one_or_none()

        if row is None:
            select_query = select(*_SELECTION_ARGS).where(
                (licensed_resources.c.licensed_resource_name == licensed_resource_name)
                & (
                    licensed_resources.c.licensed_resource_type
                    == licensed_resource_type
                )
            )

            result = await conn.execute(select_query)
            row = result.one()

        assert row is not None  # nosec
        return LicensedResourceDB.model_validate(row)


async def get_by_resource_identifier(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    licensed_resource_name: str,
    licensed_resource_type: LicensedResourceType,
) -> LicensedResourceDB:
    select_query = select(*_SELECTION_ARGS).where(
        (licensed_resources.c.licensed_resource_name == licensed_resource_name)
        & (licensed_resources.c.licensed_resource_type == licensed_resource_type)
    )

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.execute(select_query)
        row = result.one_or_none()
        if row is None:
            raise LicensedResourceNotFoundError(
                licensed_item_id="Unkown",  # <-- NOTE: will be changed for licensed_resource_id
                licensed_resource_name=licensed_resource_name,
                licensed_resource_type=licensed_resource_type,
            )
        return LicensedResourceDB.model_validate(row)
