"""
    Access to postgres database scicrunch_resources table where USED rrids get stored
"""

import logging

import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.result import ResultProxy, RowProxy
from simcore_postgres_database.models.scicrunch_resources import scicrunch_resources
from sqlalchemy.dialects.postgresql import insert as sa_pg_insert

from ..db.plugin import get_database_engine
from .models import ResearchResource, ResearchResourceAtdB

logger = logging.getLogger(__name__)


class ResearchResourceRepository:
    """Hides interaction with scicrunch_resources pg tables
    - acquires & releases connection **per call**
    - uses aiopg[sa]
    - implements CRUD on rrids
    """

    # WARNING: interfaces to both ResarchResource and ResearchResourceAtDB

    def __init__(self, app: web.Application):
        self._engine = get_database_engine(app)

    async def list_resources(self) -> list[ResearchResource]:
        async with self._engine.acquire() as conn:
            stmt = sa.select(
                [
                    scicrunch_resources.c.rrid,
                    scicrunch_resources.c.name,
                    scicrunch_resources.c.description,
                ]
            )
            res: ResultProxy = await conn.execute(stmt)
            rows: list[RowProxy] = await res.fetchall()
            return [ResearchResource.model_validate(row) for row in rows] if rows else []

    async def get(self, rrid: str) -> ResearchResourceAtdB | None:
        async with self._engine.acquire() as conn:
            stmt = sa.select(scicrunch_resources).where(
                scicrunch_resources.c.rrid == rrid
            )
            rows = await conn.execute(stmt)
            row = await rows.fetchone()
            return ResearchResourceAtdB(**row) if row else None

    async def get_resource(self, rrid: str) -> ResearchResource | None:
        resource: ResearchResourceAtdB | None = await self.get(rrid)
        if resource:
            return ResearchResource(**resource.model_dump())
        return resource

    async def upsert(self, resource: ResearchResource):
        async with self._engine.acquire() as conn:
            values = resource.model_dump(exclude_unset=True)

            stmt = (
                sa_pg_insert(scicrunch_resources)
                .values(values)
                .on_conflict_do_update(
                    index_elements=[
                        scicrunch_resources.c.rrid,
                    ],
                    set_=values,
                )
            )
            await conn.execute(stmt)
