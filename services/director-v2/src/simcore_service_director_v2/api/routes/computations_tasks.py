""" CRUD operations on a computation's tasks sub-resource

A task is computation sub-resource that respresents a running computational service in the pipeline described above
Therefore,
 - the task ID is the same as the associated node uuid

"""

import logging
from typing import NamedTuple

import networkx as nx
from fastapi import APIRouter, Depends, HTTPException
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from simcore_sdk.node_ports_v2 import FileLinkType
from starlette import status

from ...models.domains.comp_pipelines import CompPipelineAtDB
from ...models.domains.comp_tasks import CompTaskAtDB
from ...models.schemas.comp_tasks import TaskLogFileGet
from ...modules.db.repositories.comp_pipelines import CompPipelinesRepository
from ...modules.db.repositories.comp_tasks import CompTasksRepository
from ...utils.dask import get_service_log_file_download_link
from ..dependencies.database import get_repository

log = logging.getLogger(__name__)

router = APIRouter()


# HELPERS -------------------------------------------------------------------


class PipelineInfo(NamedTuple):
    # NOTE: kept old names for legacy but should rename for clarity
    pipeline_dag: nx.DiGraph
    all_tasks: list[CompTaskAtDB]  # all nodes in pipeline
    filtered_tasks: list[CompTaskAtDB]  # nodes that actually run i.e. part of the dag


async def analyze_pipeline(
    project_id: ProjectID,
    comp_pipelines_repo: CompPipelinesRepository,
    comp_tasks_repo: CompTasksRepository,
) -> PipelineInfo:
    """
    Loads and validates data from pipelines and tasks tables and
    reports it back as PipelineInfo
    """

    # NOTE: Here it is assumed the project exists in comp_tasks/comp_pipeline
    # get the project pipeline
    pipeline_at_db: CompPipelineAtDB = await comp_pipelines_repo.get_pipeline(
        project_id
    )
    pipeline_dag: nx.DiGraph = pipeline_at_db.get_graph()

    # get the project task states
    all_tasks: list[CompTaskAtDB] = await comp_tasks_repo.get_all_tasks(project_id)

    # filter the tasks by the effective pipeline
    filtered_tasks = [
        t for t in all_tasks if f"{t.node_id}" in set(pipeline_dag.nodes())
    ]

    # check that we have the expected tasks
    if len(filtered_tasks) != len(pipeline_dag):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The tasks referenced by the pipeline are missing",
        )

    return PipelineInfo(pipeline_dag, all_tasks, filtered_tasks)


# ROUTES HANDLERS --------------------------------------------------------------


@router.get(
    "/{project_id}/tasks/-/logfile",
    summary="Gets computation task logs file after is done",
    response_model=list[TaskLogFileGet],
)
async def get_all_tasks_log_files(
    user_id: UserID,
    project_id: ProjectID,
    comp_pipelines_repo: CompPipelinesRepository = Depends(
        get_repository(CompPipelinesRepository)
    ),
    comp_tasks_repo: CompTasksRepository = Depends(get_repository(CompTasksRepository)),
) -> list[TaskLogFileGet]:
    """If a computation is done, it returns download links to log-files of
    each task in a computation
    """
    result = []

    # gets computation task ids
    info = await analyze_pipeline(project_id, comp_pipelines_repo, comp_tasks_repo)

    for node_id in (t.node_id for t in info.filtered_tasks):
        # FIXME: raises NodeportsException
        log_file_url = await get_service_log_file_download_link(
            user_id, project_id, node_id, file_link_type=FileLinkType.PRESIGNED
        )

        result.append(
            TaskLogFileGet.construct(task_id=node_id, download_link=log_file_url)
        )

    return result


@router.get(
    "/{project_id}/tasks/{node_uuid}/logfile",
    summary="Gets computation task logs file after is done",
    response_model=TaskLogFileGet,
)
async def get_task_logs_file(
    user_id: UserID, project_id: ProjectID, node_uuid: NodeID
) -> TaskLogFileGet:
    """If a computation is done, it returns a link to download logs file of each task"""

    # TODO: check valid node in projectid??

    # FIXME: raises NodeportsException
    log_file_url = await get_service_log_file_download_link(
        user_id, project_id, node_uuid, file_link_type=FileLinkType.PRESIGNED
    )

    return TaskLogFileGet.construct(task_id=node_uuid, download_link=log_file_url)


@router.get(
    "/{project_id}/tasks/{node_uuid}/logs",
    summary="Gets computation task log",
)
async def get_task_logs(
    user_id: UserID, project_id: ProjectID, node_uuid: NodeID
) -> str:
    """Gets ``stdout`` and ``stderr`` logs from a computation task. It can return a list of the tail or stream live"""
    # TODO: as close as possible to https://docs.docker.com/engine/api/v1.41/#operation/ContainerTop
    raise NotImplementedError(f"/{project_id=}/tasks/{node_uuid=}/logs")
