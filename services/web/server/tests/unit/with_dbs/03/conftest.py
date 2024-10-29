# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from collections.abc import AsyncIterator

import aiopg.sa
import pytest
from simcore_postgres_database.models.user_preferences import user_preferences_frontend


@pytest.fixture
async def drop_all_preferences(
    aiopg_engine: aiopg.sa.engine.Engine,
) -> AsyncIterator[None]:
    yield
    async with aiopg_engine.acquire() as conn:
        await conn.execute(user_preferences_frontend.delete())
