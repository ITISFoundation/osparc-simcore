"""
    Models and client calls to K-Core's scicrunch API (https://scicrunch.org/api/)
"""
# TODO: not happy at all with this!!


import logging

import sqlalchemy as sa
from aiohttp import web
from servicelib.application_keys import APP_DB_ENGINE_KEY

from .db_models import scicrunch_resources
from .scicrunch_models import ResourceView

logger = logging.getLogger(__name__)


class ResearchResourceRepository:
    """Hides interaction with scicrunch_resources pg tables
    - acquires & releases connection **per call**
    - uses aiopg[sa]
    """

    def __init__(self, app: web.Application):
        self._engine = app[APP_DB_ENGINE_KEY]
        # TODO: acquire member to monitor connections

    async def create(self, resource: ResourceView):
        async with self._engine.acquire() as conn:
            pass

    async def get(self, rrid: str) -> ResourceView:
        async with self._engine.acquire() as conn:
            stmt = sa.select([scicrunch_resources]).where(
                scicrunch_resources.c.rrid == rrid
            )
            rows = await conn.execute(stmt)
            row = await rows.fetchone()
            return ResourceView(**row)  # ???

    async def update(self, resource: ResourceView):
        pass
