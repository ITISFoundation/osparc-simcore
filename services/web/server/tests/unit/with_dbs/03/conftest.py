# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from collections.abc import AsyncIterator

import pytest
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_postgres_database.models.user_preferences import user_preferences_frontend
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
async def drop_all_preferences(
    asyncpg_engine: AsyncEngine,
) -> AsyncIterator[None]:
    yield
    async with asyncpg_engine.connect() as conn:
        await conn.execute(user_preferences_frontend.delete())


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            # disable tracing  for tests
            "TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT": "null",
            "TRACING_OPENTELEMETRY_COLLECTOR_PORT": "null",
            "WEBSERVER_TRACING": "null",
        },
    )
