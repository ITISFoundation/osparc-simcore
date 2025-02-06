from collections.abc import AsyncIterator

# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import pytest
from aiohttp.test_utils import TestClient
from simcore_postgres_database.models.licensed_items import licensed_items
from simcore_postgres_database.models.resource_tracker_pricing_plans import (
    resource_tracker_pricing_plans,
)
from simcore_postgres_database.utils_repos import transaction_context
from simcore_service_webserver.db.plugin import get_asyncpg_engine


@pytest.fixture
async def pricing_plan_id(
    client: TestClient,
    osparc_product_name: str,
) -> AsyncIterator[int]:
    assert client.app

    async with transaction_context(get_asyncpg_engine(client.app)) as conn:
        result = await conn.execute(
            resource_tracker_pricing_plans.insert()
            .values(
                product_name=osparc_product_name,
                display_name="ISolve Thermal",
                description="",
                classification="TIER",
                is_active=True,
                pricing_plan_key="isolve-thermal",
            )
            .returning(resource_tracker_pricing_plans.c.pricing_plan_id)
        )
        row = result.one()

    assert row

    yield int(row[0])

    async with transaction_context(get_asyncpg_engine(client.app)) as conn:
        await conn.execute(licensed_items.delete())
        await conn.execute(resource_tracker_pricing_plans.delete())


@pytest.fixture
async def ensure_empty_licensed_items(client: TestClient):
    async def _cleanup():
        assert client.app
        async with transaction_context(get_asyncpg_engine(client.app)) as conn:
            await conn.execute(licensed_items.delete())

    await _cleanup()

    yield

    await _cleanup()
