# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from collections.abc import AsyncIterator
from typing import Any

import pytest
import sqlalchemy as sa
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
    docker_compose_service_environment_dict: EnvVarsDict,
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            **docker_compose_service_environment_dict,
            # disable tracing  for tests
            "TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT": "null",
            "TRACING_OPENTELEMETRY_COLLECTOR_PORT": "null",
            "WEBSERVER_TRACING": "null",
            "WEBSERVER_RPC_NAMESPACE": "null",
        },
    )


@pytest.fixture
async def support_group_before_app_starts(
    asyncpg_engine: AsyncEngine,
    product_name: str,
) -> AsyncIterator[dict[str, Any]]:
    """Creates a standard support group and assigns it to the current product

    NOTE: this has to be added BEFORE any client fixture in the tests
    """
    from pytest_simcore.helpers.postgres_tools import insert_and_get_row_lifespan
    from simcore_postgres_database.models.groups import groups
    from simcore_postgres_database.models.products import products

    # Create support group using direct database insertion
    group_values = {
        "name": "Support Group",
        "description": "Support group for product",
        "type": "STANDARD",
    }

    # pylint: disable=contextmanager-generator-missing-cleanup
    async with insert_and_get_row_lifespan(
        asyncpg_engine,
        table=groups,
        values=group_values,
        pk_col=groups.c.gid,
    ) as group_row:
        group_id = group_row["gid"]

        # Update product to set support_standard_group_id
        async with asyncpg_engine.begin() as conn:
            await conn.execute(
                sa.update(products)
                .where(products.c.name == product_name)
                .values(support_standard_group_id=group_id)
            )

        yield group_row
        # group will be deleted after test
