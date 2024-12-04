from dataclasses import dataclass
from typing import Any, Callable

import aiopg
import aiopg.sa
import sqlalchemy as sa
from models_library.projects import ProjectAtDB, ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from pydantic import TypeAdapter
from simcore_postgres_database.models.comp_runs import comp_runs
from simcore_postgres_database.models.comp_tasks import comp_tasks
from simcore_service_director_v2.models.comp_pipelines import CompPipelineAtDB
from simcore_service_director_v2.models.comp_runs import CompRunsAtDB
from simcore_service_director_v2.models.comp_tasks import CompTaskAtDB
from sqlalchemy.ext.asyncio import AsyncEngine


@dataclass
class PublishedProject:
    user: dict[str, Any]
    project: ProjectAtDB
    pipeline: CompPipelineAtDB
    tasks: list[CompTaskAtDB]


@dataclass(kw_only=True)
class RunningProject(PublishedProject):
    runs: CompRunsAtDB
    task_to_callback_mapping: dict[NodeID, Callable[[], None]]


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
    expected_state: RunningState | None = None,
    where_statement: Any | None = None,
) -> list[CompRunsAtDB]:
    async with sqlalchemy_async_engine.connect() as conn:
        query = sa.select(comp_runs)
        if where_statement is not None:
            query = query.where(where_statement)
        list_of_comp_runs = [
            CompRunsAtDB.model_validate(row) for row in await conn.execute(query)
        ]
    assert len(list_of_comp_runs) == expected_total
    if list_of_comp_runs and expected_state:
        assert all(
            r.result is expected_state for r in list_of_comp_runs
        ), f"expected state '{expected_state}', got {[r.result for r in list_of_comp_runs]}"
    return list_of_comp_runs


async def assert_comp_runs_empty(sqlalchemy_async_engine: AsyncEngine) -> None:
    await assert_comp_runs(sqlalchemy_async_engine, expected_total=0)


async def assert_comp_tasks(
    sqlalchemy_async_engine: AsyncEngine,
    *,
    project_uuid: ProjectID,
    task_ids: list[NodeID],
    expected_state: RunningState,
    expected_progress: float | None,
) -> list[CompTaskAtDB]:
    # check the database is correctly updated, the run is published
    async with sqlalchemy_async_engine.connect() as conn:
        result = await conn.execute(
            comp_tasks.select().where(
                (comp_tasks.c.project_id == f"{project_uuid}")
                & (comp_tasks.c.node_id.in_([f"{n}" for n in task_ids]))
            )  # there is only one entry
        )
        tasks = TypeAdapter(list[CompTaskAtDB]).validate_python(result.fetchall())
    assert all(
        t.state == expected_state for t in tasks
    ), f"expected state: {expected_state}, found: {[t.state for t in tasks]}"
    assert all(
        t.progress == expected_progress for t in tasks
    ), f"{expected_progress=}, found: {[t.progress for t in tasks]}"
    return tasks
