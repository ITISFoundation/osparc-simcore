"""
Repository for scicrunch_resources table operations using asyncpg
"""

import logging
from typing import Any

import sqlalchemy as sa
from simcore_postgres_database.models.scicrunch_resources import scicrunch_resources
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy.dialects.postgresql import insert as sa_pg_insert
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncConnection

from ..db.base_repository import BaseRepository

_logger = logging.getLogger(__name__)


class ScicrunchResourcesRepository(BaseRepository):
    """Repository for managing scicrunch_resources operations."""

    async def list_all_resources(self, connection: AsyncConnection | None = None) -> list[Row]:
        """List all research resources with basic fields."""
        async with pass_or_acquire_connection(self.engine, connection) as conn:
            stmt = sa.select(
                scicrunch_resources.c.rrid,
                scicrunch_resources.c.name,
                scicrunch_resources.c.description,
            )
            result = await conn.execute(stmt)
            return result.fetchall()

    async def get_resource_by_rrid(self, rrid: str, connection: AsyncConnection | None = None) -> Row | None:
        """Get a research resource by RRID."""
        async with pass_or_acquire_connection(self.engine, connection) as conn:
            stmt = sa.select(scicrunch_resources).where(scicrunch_resources.c.rrid == rrid)
            result = await conn.execute(stmt)
            return result.one_or_none()

    async def upsert_resource(self, resource_data: dict[str, Any], connection: AsyncConnection | None = None) -> Row:
        """Insert or update a research resource."""
        async with transaction_context(self.engine, connection) as conn:
            stmt = (
                sa_pg_insert(scicrunch_resources)
                .values(resource_data)
                .on_conflict_do_update(
                    index_elements=[scicrunch_resources.c.rrid],
                    set_=resource_data,
                )
                .returning(*scicrunch_resources.c)
            )
            result = await conn.execute(stmt)
            return result.one()
