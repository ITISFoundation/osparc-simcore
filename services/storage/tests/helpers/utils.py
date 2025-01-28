import logging
import os
from typing import Any

import sqlalchemy as sa
from simcore_postgres_database.storage_models import projects
from sqlalchemy.ext.asyncio import AsyncEngine

log = logging.getLogger(__name__)


def has_datcore_tokens() -> bool:
    api_key = os.environ.get("BF_API_KEY")
    api_secret = os.environ.get("BF_API_SECRET")
    if not api_key or not api_secret:
        return False
    return not (api_key == "none" or api_secret == "none")  # noqa: S105


async def get_updated_project(
    sqlalchemy_async_engine: AsyncEngine, project_id: str
) -> dict[str, Any]:
    async with sqlalchemy_async_engine.connect() as conn:
        result = await conn.execute(
            sa.select(projects).where(projects.c.uuid == project_id)
        )
        row = result.fetchone()
        assert row
        return dict(row)
