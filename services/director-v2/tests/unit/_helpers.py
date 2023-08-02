import asyncio
from dataclasses import dataclass
from typing import Any

import aiopg
import aiopg.sa
from models_library.projects import ProjectAtDB
from models_library.projects_nodes_io import NodeID
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_postgres_database.models.comp_tasks import comp_tasks
from simcore_service_director_v2.models.comp_pipelines import CompPipelineAtDB
from simcore_service_director_v2.models.comp_runs import CompRunsAtDB
from simcore_service_director_v2.models.comp_tasks import CompTaskAtDB
from simcore_service_director_v2.modules.comp_scheduler.base_scheduler import (
    BaseCompScheduler,
)


@dataclass
class PublishedProject:
    project: ProjectAtDB
    pipeline: CompPipelineAtDB
    tasks: list[CompTaskAtDB]


@dataclass
class RunningProject(PublishedProject):
    runs: CompRunsAtDB


async def trigger_comp_scheduler(scheduler: BaseCompScheduler) -> None:
    # trigger the scheduler
    scheduler._wake_up_scheduler_now()  # pylint: disable=protected-access
    # let the scheduler be actually triggered
    await asyncio.sleep(1)


async def set_comp_task_state(
    aiopg_engine: aiopg.sa.engine.Engine, node_id: str, state: StateType
) -> None:
    async with aiopg_engine.acquire() as conn:
        await conn.execute(
            comp_tasks.update()
            .where(comp_tasks.c.node_id == node_id)
            .values(state=state)
        )


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
