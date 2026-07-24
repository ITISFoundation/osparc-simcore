# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint:disable=contextmanager-generator-missing-cleanup

import json
from contextlib import AsyncExitStack

import pytest
from pytest_simcore.helpers.faker_factories import (
    fake_pipeline,
    fake_task_factory,
    random_project,
)
from pytest_simcore.helpers.postgres_products import insert_and_get_product_lifespan
from pytest_simcore.helpers.postgres_tools import insert_and_get_row_lifespan
from simcore_postgres_database.models.comp_pipeline import comp_pipeline
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.webserver_models import comp_tasks
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

fake_task = fake_task_factory(first_internal_id=1)


async def test_unique_project_node_pairs(asyncpg_engine: AsyncEngine):
    async with AsyncExitStack() as stack:
        product = await stack.enter_async_context(insert_and_get_product_lifespan(asyncpg_engine))

        project_a = await stack.enter_async_context(
            insert_and_get_row_lifespan(
                asyncpg_engine,
                table=projects,
                values=random_project(product_name=product["name"], prj_owner=None),
                pk_col=projects.c.uuid,
            )
        )
        project_b = await stack.enter_async_context(
            insert_and_get_row_lifespan(
                asyncpg_engine,
                table=projects,
                values=random_project(product_name=product["name"], prj_owner=None),
                pk_col=projects.c.uuid,
            )
        )

        for project in (project_a, project_b):
            await stack.enter_async_context(
                insert_and_get_row_lifespan(
                    asyncpg_engine,
                    table=comp_pipeline,
                    values=fake_pipeline(project_id=project["uuid"]),
                    pk_col=comp_pipeline.c.project_id,
                )
            )

        task_1 = await stack.enter_async_context(
            insert_and_get_row_lifespan(
                asyncpg_engine,
                table=comp_tasks,
                values=fake_task(project_id=project_a["uuid"], node_id="N1"),
                pk_col=comp_tasks.c.task_id,
            )
        )
        assert task_1["task_id"] == 1

        task_2 = await stack.enter_async_context(
            insert_and_get_row_lifespan(
                asyncpg_engine,
                table=comp_tasks,
                values=fake_task(project_id=project_a["uuid"], node_id="N2"),
                pk_col=comp_tasks.c.task_id,
            )
        )
        assert task_2["task_id"] == 2

        task_3 = await stack.enter_async_context(
            insert_and_get_row_lifespan(
                asyncpg_engine,
                table=comp_tasks,
                values=fake_task(project_id=project_b["uuid"], node_id="N2"),
                pk_col=comp_tasks.c.task_id,
            )
        )
        assert task_3["task_id"] == 3
        assert json.loads(task_3["inputs"]) == {}

        async with asyncpg_engine.connect() as conn:
            with pytest.raises(IntegrityError, match="project_node_uniqueness"):
                await conn.execute(comp_tasks.insert().values(**fake_task(project_id=project_a["uuid"], node_id="N1")))
