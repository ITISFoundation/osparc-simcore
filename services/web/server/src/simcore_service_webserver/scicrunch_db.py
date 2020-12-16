"""
    Access to postgres database scicrunch_resources table where USED rrids get stored
"""

import logging
from typing import Optional

import sqlalchemy as sa
from aiohttp import web
from servicelib.application_keys import APP_DB_ENGINE_KEY

from .db_models import scicrunch_resources
from .scicrunch_models import ResearchResource, ResearchResourceAtdB

logger = logging.getLogger(__name__)


class ResearchResourceRepository:
    """Hides interaction with scicrunch_resources pg tables
    - acquires & releases connection **per call**
    - uses aiopg[sa]
    - implements CRUD on rrids
    """

    def __init__(self, app: web.Application):
        self._engine = app[APP_DB_ENGINE_KEY]
        # TODO: acquire member to monitor connections

    async def get(self, rrid: str) -> Optional[ResearchResourceAtdB]:
        async with self._engine.acquire() as conn:
            stmt = sa.select([scicrunch_resources]).where(
                scicrunch_resources.c.rrid == rrid
            )
            rows = await conn.execute(stmt)
            row = await rows.fetchone()
            return ResearchResourceAtdB(**row) if row else None

    async def get_resource(self, rrid: str) -> Optional[ResearchResource]:
        resource = await self.get(rrid)
        if resource:
            return ResearchResource(**resource.dict())
        return resource

    async def upsert(self, vals: ResearchResource):
        async with self._engine.acquire() as conn:
            values = vals.dict(exclude_unset=True)

            stmt = (
                sa.insert(scicrunch_resources)
                .values(values)
                .on_conflict_do_update(
                    index_elements=[
                        scicrunch_resources.c.rrid,
                        scicrunch_resources.c.name,
                        scicrunch_resources.c.description,
                    ],
                    set_=values,
                )
            )
            await conn.execute(stmt)
