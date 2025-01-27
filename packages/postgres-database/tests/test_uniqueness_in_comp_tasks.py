# pylint:disable=no-value-for-parameter
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
from collections.abc import Awaitable, Callable

import aiopg.sa.engine
import aiopg.sa.exc
import pytest
import sqlalchemy as sa
from psycopg2.errors import UniqueViolation  # pylint: disable=no-name-in-module
from pytest_simcore.helpers import postgres_tools
from pytest_simcore.helpers.faker_factories import fake_pipeline, fake_task_factory
from simcore_postgres_database.models.base import metadata
from simcore_postgres_database.webserver_models import comp_pipeline, comp_tasks

fake_task = fake_task_factory(first_internal_id=1)


@pytest.fixture
async def engine(
    make_engine: Callable[[bool], Awaitable[aiopg.sa.engine.Engine] | sa.engine.Engine]
):
    async_engine: aiopg.sa.engine.Engine = await make_engine(is_async=True)
    sync_engine: sa.engine.Engine = make_engine(is_async=False)
    metadata.drop_all(sync_engine)
    metadata.create_all(sync_engine)

    async with async_engine.acquire() as conn:
        await conn.execute(
            comp_pipeline.insert().values(**fake_pipeline(project_id="PA"))
        )
        await conn.execute(
            comp_pipeline.insert().values(**fake_pipeline(project_id="PB"))
        )

    yield async_engine

    try:
        postgres_tools.drop_all_tables(sync_engine)
    finally:
        sync_engine.dispose()

    async_engine.close()
    await async_engine.wait_closed()


async def test_unique_project_node_pairs(engine):
    async with engine.acquire() as conn:
        task_id = await conn.scalar(
            comp_tasks.insert().values(**fake_task(project_id="PA", node_id="N1"))
        )
        assert task_id == 1

        assert (
            await conn.scalar(
                comp_tasks.insert().values(**fake_task(project_id="PA", node_id="N2"))
            )
            == 2
        )

        assert (
            await conn.scalar(
                comp_tasks.insert().values(**fake_task(project_id="PB", node_id="N2"))
            )
            == 3
        )

        task_inputs = await conn.scalar(
            sa.select(comp_tasks.c.inputs).where(
                sa.and_(
                    comp_tasks.c.project_id == "PB",
                    comp_tasks.c.node_id == "N2",
                )
            )
        )
        assert json.loads(task_inputs) == {}

        with pytest.raises(UniqueViolation, match="project_node_uniqueness"):
            #
            # psycopg2.errors.UniqueViolation:
            #   duplicate key value violates unique constraint "project_node_uniqueness" ...
            #
            await conn.execute(
                comp_tasks.insert().values(**fake_task(project_id="PA", node_id="N1"))
            )
