from typing import AsyncIterator

import aiopg.sa
import pytest
from simcore_postgres_database.models.user_preferences import user_preferences


@pytest.fixture
async def drop_all_preferences(
    aiopg_engine: aiopg.sa.engine.Engine,
) -> AsyncIterator[None]:
    yield
    async with aiopg_engine.acquire() as conn:
        await conn.execute(user_preferences.delete())
