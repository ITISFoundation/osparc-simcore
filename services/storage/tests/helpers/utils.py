import logging
import os
from typing import Any

import sqlalchemy as sa
from simcore_postgres_database.storage_models import projects
from sqlalchemy.ext.asyncio import AsyncEngine

log = logging.getLogger(__name__)


def has_datcore_tokens() -> bool:
    # TODO: activate tests against BF services in the CI.
    #
    # CI shall add BF_API_KEY, BF_API_SECRET environs as secrets
    #
    if not os.environ.get("BF_API_KEY") or not os.environ.get("BF_API_SECRET"):
        return False
    return True


async def get_updated_project(
    sqlalchemy_async_engine: AsyncEngine, project_id: str
) -> dict[str, Any]:
    async with aiopg_engine.connect() as conn:
        result = await conn.execute(
            sa.select(projects).where(projects.c.uuid == project_id)
        )
        row = await result.fetchone()
        assert row
        return dict(row)
