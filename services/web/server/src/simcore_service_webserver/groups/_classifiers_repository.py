import logging
from typing import Any, cast

import sqlalchemy as sa
from simcore_postgres_database.models.classifiers import group_classifiers
from simcore_postgres_database.utils_repos import pass_or_acquire_connection
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncConnection

from ..db.base_repository import BaseRepository

_logger = logging.getLogger(__name__)


class GroupClassifierRepository(BaseRepository):
    async def _get_bundle(self, gid: int, connection: AsyncConnection | None = None) -> Row | None:
        async with pass_or_acquire_connection(self.engine, connection) as conn:
            result = await conn.execute(sa.select(group_classifiers.c.bundle).where(group_classifiers.c.gid == gid))
            return result.one_or_none()

    async def get_classifiers_from_bundle(self, gid: int) -> dict[str, Any] | None:
        bundle_row = await self._get_bundle(gid)
        if bundle_row:
            return cast(dict[str, Any], bundle_row.bundle)
        return None

    async def group_uses_scicrunch(self, gid: int, connection: AsyncConnection | None = None) -> bool:
        async with pass_or_acquire_connection(self.engine, connection) as conn:
            result = await conn.execute(
                sa.select(group_classifiers.c.uses_scicrunch).where(group_classifiers.c.gid == gid)
            )
            row = result.one_or_none()
            return bool(row.uses_scicrunch if row else False)
