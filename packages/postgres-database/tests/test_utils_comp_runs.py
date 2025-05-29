# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
import datetime

import pytest
import sqlalchemy as sa
from simcore_postgres_database.models.comp_runs import comp_runs
from simcore_postgres_database.utils_comp_runs import get_latest_run_id_for_project
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
async def sample_comp_runs(asyncpg_engine: AsyncEngine):
    async with asyncpg_engine.begin() as conn:
        await conn.execute(sa.text("SET session_replication_role = replica;"))
        await conn.execute(sa.delete(comp_runs))
        await conn.execute(
            comp_runs.insert(),
            [
                {
                    "run_id": 1,
                    "project_uuid": "project-1",
                    "user_id": 10,
                    "iteration": 1,
                    "result": "NOT_STARTED",
                    "created": datetime.datetime(
                        2024, 1, 1, 10, 0, 0, tzinfo=datetime.UTC
                    ),
                    "modified": datetime.datetime(
                        2024, 1, 1, 10, 0, 0, tzinfo=datetime.UTC
                    ),
                    "started": None,
                    "ended": None,
                    "cancelled": None,
                    "scheduled": None,
                    "processed": None,
                    "metadata": None,
                    "use_on_demand_clusters": False,
                    "dag_adjacency_list": {},
                },
                {
                    "run_id": 2,
                    "project_uuid": "project-1",
                    "user_id": 10,
                    "iteration": 2,
                    "result": "NOT_STARTED",
                    "created": datetime.datetime(
                        2024, 1, 1, 11, 0, 0, tzinfo=datetime.UTC
                    ),
                    "modified": datetime.datetime(
                        2024, 1, 1, 11, 0, 0, tzinfo=datetime.UTC
                    ),
                    "started": None,
                    "ended": None,
                    "cancelled": None,
                    "scheduled": None,
                    "processed": None,
                    "metadata": None,
                    "use_on_demand_clusters": False,
                    "dag_adjacency_list": {},
                },
                {
                    "run_id": 3,
                    "project_uuid": "project-1",
                    "user_id": 20,
                    "iteration": 1,
                    "result": "NOT_STARTED",
                    "created": datetime.datetime(
                        2024, 1, 1, 12, 0, 0, tzinfo=datetime.UTC
                    ),
                    "modified": datetime.datetime(
                        2024, 1, 1, 12, 0, 0, tzinfo=datetime.UTC
                    ),
                    "started": None,
                    "ended": None,
                    "cancelled": None,
                    "scheduled": None,
                    "processed": None,
                    "metadata": None,
                    "use_on_demand_clusters": False,
                    "dag_adjacency_list": {},
                },
                {
                    "run_id": 4,
                    "project_uuid": "project-2",
                    "user_id": 30,
                    "iteration": 1,
                    "result": "NOT_STARTED",
                    "created": datetime.datetime(
                        2024, 1, 1, 13, 0, 0, tzinfo=datetime.UTC
                    ),
                    "modified": datetime.datetime(
                        2024, 1, 1, 13, 0, 0, tzinfo=datetime.UTC
                    ),
                    "started": None,
                    "ended": None,
                    "cancelled": None,
                    "scheduled": None,
                    "processed": None,
                    "metadata": None,
                    "use_on_demand_clusters": False,
                    "dag_adjacency_list": {},
                },
            ],
        )
        await conn.execute(sa.text("SET session_replication_role = DEFAULT;"))
    yield
    async with asyncpg_engine.begin() as conn:
        await conn.execute(sa.text("SET session_replication_role = replica;"))
        await conn.execute(sa.delete(comp_runs))
        await conn.execute(sa.text("SET session_replication_role = DEFAULT;"))


async def test_get_latest_run_id_for_project(
    asyncpg_engine: AsyncEngine, sample_comp_runs: None
):
    run_id = await get_latest_run_id_for_project(asyncpg_engine, project_id="project-1")
    assert run_id == 3

    run_id2 = await get_latest_run_id_for_project(
        asyncpg_engine, project_id="project-2"
    )
    assert run_id2 == 4


async def test_get_latest_run_id_for_project_no_runs(
    asyncpg_engine: AsyncEngine, sample_comp_runs: None
):
    import uuid

    output = await get_latest_run_id_for_project(
        asyncpg_engine, project_id=str(uuid.uuid4())
    )
    assert output is None
