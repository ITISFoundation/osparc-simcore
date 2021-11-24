import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List

import aiopg
from models_library.projects import ProjectAtDB, ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from pydantic.tools import parse_obj_as
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_postgres_database.models.comp_runs import comp_runs
from simcore_postgres_database.models.comp_tasks import comp_tasks
from simcore_service_director_v2.models.domains.comp_pipelines import CompPipelineAtDB
from simcore_service_director_v2.models.domains.comp_runs import CompRunsAtDB
from simcore_service_director_v2.models.domains.comp_tasks import CompTaskAtDB
from simcore_service_director_v2.models.schemas.constants import UserID
from simcore_service_director_v2.modules.comp_scheduler.base_scheduler import (
    BaseCompScheduler,
)


@dataclass
class PublishedProject:
    project: ProjectAtDB
    pipeline: CompPipelineAtDB
    tasks: List[CompTaskAtDB]


async def assert_comp_run_state(
    aiopg_engine: Iterator[aiopg.sa.engine.Engine],  # type: ignore
    user_id: UserID,
    project_uuid: ProjectID,
    exp_state: RunningState,
):
    # check the database is correctly updated, the run is published
    async with aiopg_engine.acquire() as conn:  # type: ignore
        result = await conn.execute(
            comp_runs.select().where(
                (comp_runs.c.user_id == user_id)
                & (comp_runs.c.project_uuid == f"{project_uuid}")
            )  # there is only one entry
        )
        run_entry = CompRunsAtDB.parse_obj(await result.first())
    assert (
        run_entry.result == exp_state
    ), f"comp_runs: expected state '{exp_state}, found '{run_entry.result}'"


async def assert_comp_tasks_state(
    aiopg_engine: Iterator[aiopg.sa.engine.Engine],  # type: ignore
    project_uuid: ProjectID,
    task_ids: List[NodeID],
    exp_state: RunningState,
):
    # check the database is correctly updated, the run is published
    async with aiopg_engine.acquire() as conn:  # type: ignore
        result = await conn.execute(
            comp_tasks.select().where(
                (comp_tasks.c.project_id == f"{project_uuid}")
                & (comp_tasks.c.node_id.in_([f"{n}" for n in task_ids]))
            )  # there is only one entry
        )
        tasks = parse_obj_as(List[CompTaskAtDB], await result.fetchall())
    assert all(  # pylint: disable=use-a-generator
        [t.state == exp_state for t in tasks]
    ), f"expected state: {exp_state}, found: {[t.state for t in tasks]}"


async def trigger_comp_scheduler(scheduler: BaseCompScheduler):
    # trigger the scheduler
    scheduler._wake_up_scheduler_now()  # pylint: disable=protected-access
    # let the scheduler be actually triggered
    await asyncio.sleep(1)


async def manually_run_comp_scheduler(scheduler: BaseCompScheduler):
    # trigger the scheduler
    await scheduler.schedule_all_pipelines()


async def set_comp_task_state(
    aiopg_engine: Iterator[aiopg.sa.engine.Engine], node_id: str, state: StateType  # type: ignore
):
    async with aiopg_engine.acquire() as conn:  # type: ignore
        await conn.execute(
            # pylint: disable=no-value-for-parameter
            comp_tasks.update()
            .where(comp_tasks.c.node_id == node_id)
            .values(state=state)
        )


async def set_comp_task_outputs(
    aiopg_engine: aiopg.sa.engine.Engine, node_id: NodeID, outputs_schema: Dict[str, Any], outputs: Dict[str, Any]  # type: ignore
):
    async with aiopg_engine.acquire() as conn:  # type: ignore
        await conn.execute(
            # pylint: disable=no-value-for-parameter
            comp_tasks.update()
            .where(comp_tasks.c.node_id == f"{node_id}")
            .values(outputs=outputs, schema={"outputs": outputs_schema, "inputs": {}})
        )


async def set_comp_task_inputs(
    aiopg_engine: aiopg.sa.engine.Engine, node_id: NodeID, inputs_schema: Dict[str, Any], inputs: Dict[str, Any]  # type: ignore
):
    async with aiopg_engine.acquire() as conn:  # type: ignore
        await conn.execute(
            # pylint: disable=no-value-for-parameter
            comp_tasks.update()
            .where(comp_tasks.c.node_id == f"{node_id}")
            .values(inputs=inputs, schema={"outputs": {}, "inputs": inputs_schema})
        )
