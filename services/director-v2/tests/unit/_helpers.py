from dataclasses import dataclass
from typing import Any

import aiopg
import aiopg.sa
import sqlalchemy as sa
from models_library.projects import ProjectAtDB
from models_library.projects_nodes_io import NodeID
from simcore_postgres_database.models.comp_runs import comp_runs
from simcore_postgres_database.models.comp_tasks import comp_tasks
from simcore_service_director_v2.models.comp_pipelines import CompPipelineAtDB
from simcore_service_director_v2.models.comp_runs import CompRunsAtDB
from simcore_service_director_v2.models.comp_tasks import CompTaskAtDB
from sqlalchemy.ext.asyncio import AsyncEngine


@dataclass
class PublishedProject:
    project: ProjectAtDB
    pipeline: CompPipelineAtDB
    tasks: list[CompTaskAtDB]


@dataclass
class RunningProject(PublishedProject):
    runs: CompRunsAtDB


async def set_comp_task_outputs(
    aiopg_engine: aiopg.sa.engine.Engine,
    node_id: NodeID,
    outputs_schema: dict[str, Any],
    outputs: dict[str, Any],
) -> None:
    async with aiopg_engine.acquire() as conn:
        await conn.execute(
            comp_tasks.update()
            .where(comp_tasks.c.node_id == f"{node_id}")
            .values(outputs=outputs, schema={"outputs": outputs_schema, "inputs": {}})
        )


async def set_comp_task_inputs(
    aiopg_engine: aiopg.sa.engine.Engine,
    node_id: NodeID,
    inputs_schema: dict[str, Any],
    inputs: dict[str, Any],
) -> None:
    async with aiopg_engine.acquire() as conn:
        await conn.execute(
            comp_tasks.update()
            .where(comp_tasks.c.node_id == f"{node_id}")
            .values(inputs=inputs, schema={"outputs": {}, "inputs": inputs_schema})
        )


async def assert_comp_runs(
    sqlalchemy_async_engine: AsyncEngine,
    *,
    expected_total: int,
    where_statement: Any | None = None,
) -> list[CompRunsAtDB]:
    async with sqlalchemy_async_engine.connect() as conn:
        query = sa.select(comp_runs)
        if where_statement is not None:
            query = query.where(where_statement)
        list_of_comp_runs = [
            CompRunsAtDB.from_orm(row) for row in await conn.execute(query)
        ]
    assert len(list_of_comp_runs) == expected_total
    return list_of_comp_runs


async def assert_comp_runs_empty(sqlalchemy_async_engine: AsyncEngine) -> None:
    await assert_comp_runs(sqlalchemy_async_engine, expected_total=0)
