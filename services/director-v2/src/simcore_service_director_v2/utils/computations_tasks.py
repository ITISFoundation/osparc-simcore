from typing import NamedTuple

import networkx as nx
from models_library.projects import ProjectID
from simcore_postgres_database.utils_repos import pass_or_acquire_connection
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from ..core.errors import PipelineTaskMissingError
from ..models.comp_pipelines import CompPipelineAtDB
from ..models.comp_tasks import CompTaskAtDB
from ..modules.db.repositories.comp_pipelines import CompPipelinesRepository
from ..modules.db.repositories.comp_tasks import CompTasksRepository


class PipelineInfo(NamedTuple):
    pipeline_dag: nx.DiGraph
    all_tasks: list[CompTaskAtDB]
    filtered_tasks: list[CompTaskAtDB]


async def _get_pipeline_info(
    db_engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    project_id: ProjectID,
) -> PipelineInfo:
    # NOTE: Here it is assumed the project exists in comp_tasks/comp_pipeline
    comp_pipelines_repo = CompPipelinesRepository(db_engine)
    comp_tasks_repo = CompTasksRepository(db_engine)

    async with pass_or_acquire_connection(db_engine, connection) as conn:
        pipeline_at_db: CompPipelineAtDB = await comp_pipelines_repo.get_pipeline(conn, project_id=project_id)
        all_tasks: list[CompTaskAtDB] = await comp_tasks_repo.list_tasks(conn, project_id=project_id)

    pipeline_dag: nx.DiGraph = pipeline_at_db.get_graph()

    # filter the tasks by the effective pipeline
    filtered_tasks = [t for t in all_tasks if f"{t.node_id}" in set(pipeline_dag.nodes())]

    return PipelineInfo(pipeline_dag, all_tasks, filtered_tasks)


async def validate_pipeline(
    db_engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    project_id: ProjectID,
) -> PipelineInfo:
    """
    Loads and validates data from pipelines and tasks tables and
    reports it back as PipelineInfo

    raises PipelineTaskMissingError
    """

    pipeline_info = await _get_pipeline_info(db_engine, connection, project_id=project_id)

    # check that we have the expected tasks
    if len(pipeline_info.filtered_tasks) != len(pipeline_info.pipeline_dag):
        raise PipelineTaskMissingError(project_id=project_id)

    return pipeline_info
