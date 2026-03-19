# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import json
from collections.abc import AsyncIterator

import pytest
import sqlalchemy as sa
import sqlalchemy.engine
from pytest_simcore.helpers import postgres_tools
from pytest_simcore.helpers.faker_factories import fake_pipeline, fake_task_factory
from simcore_postgres_database.models.base import metadata
from simcore_postgres_database.webserver_models import comp_pipeline, comp_tasks
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

fake_task = fake_task_factory(first_internal_id=1)


@pytest.fixture
async def engine(
    sync_engine: sqlalchemy.engine.Engine,
    asyncpg_engine: AsyncEngine,
) -> AsyncIterator[AsyncEngine]:
    metadata.drop_all(sync_engine)
    metadata.create_all(sync_engine)

    async with asyncpg_engine.connect() as conn:
        await conn.execution_options(isolation_level="AUTOCOMMIT")
        await conn.execute(comp_pipeline.insert().values(**fake_pipeline(project_id="PA")))
        await conn.execute(comp_pipeline.insert().values(**fake_pipeline(project_id="PB")))

    yield asyncpg_engine

    postgres_tools.force_drop_all_tables(sync_engine)


async def test_unique_project_node_pairs(engine: AsyncEngine):
    async with engine.connect() as conn:
        await conn.execution_options(isolation_level="AUTOCOMMIT")

        task_id = await conn.scalar(comp_tasks.insert().values(**fake_task(project_id="PA", node_id="N1")))
        assert task_id == 1

        assert await conn.scalar(comp_tasks.insert().values(**fake_task(project_id="PA", node_id="N2"))) == 2

        assert await conn.scalar(comp_tasks.insert().values(**fake_task(project_id="PB", node_id="N2"))) == 3

        task_inputs = await conn.scalar(
            sa.select(comp_tasks.c.inputs).where(
                sa.and_(
                    comp_tasks.c.project_id == "PB",
                    comp_tasks.c.node_id == "N2",
                )
            )
        )
        assert json.loads(task_inputs) == {}

        with pytest.raises(IntegrityError, match="project_node_uniqueness"):
            #
            # psycopg2.errors.UniqueViolation:
            #   duplicate key value violates unique constraint "project_node_uniqueness" ...
            #
            await conn.execute(comp_tasks.insert().values(**fake_task(project_id="PA", node_id="N1")))
