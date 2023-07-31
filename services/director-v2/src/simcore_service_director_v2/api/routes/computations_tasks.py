""" CRUD operations on a computation's tasks sub-resource

A task is computation sub-resource that respresents a running computational service in the pipeline described above
Therefore,
 - the task ID is the same as the associated node uuid

"""

import logging
from typing import NamedTuple

import networkx as nx
from fastapi import APIRouter, Depends, HTTPException
from models_library.api_schemas_directorv2.comp_tasks import TaskLogFileGet
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from servicelib.utils import logged_gather
from simcore_sdk.node_ports_common.exceptions import NodeportsException
from simcore_sdk.node_ports_v2 import FileLinkType
from starlette import status

from ...models.domains.comp_pipelines import CompPipelineAtDB
from ...models.domains.comp_tasks import CompTaskAtDB
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
    all_tasks: list[CompTaskAtDB] = await comp_tasks_repo.list_tasks(project_id)

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


async def _get_task_log_file(
    user_id: UserID, project_id: ProjectID, node_id: NodeID
) -> TaskLogFileGet:
    try:
        log_file_url = await get_service_log_file_download_link(
            user_id, project_id, node_id, file_link_type=FileLinkType.PRESIGNED
        )

    except NodeportsException as err:
        # Unexpected error: Cannot determine the cause of failure
        # to get donwload link and cannot handle it automatically.
        # Will treat it as "not available" and log a warning
        log_file_url = None
        log.warning(
            "Failed to get log-file of %s: %s.",
            f"{user_id=}/{project_id=}/{node_id=}",
            err,
        )

    return TaskLogFileGet(
        task_id=node_id,
        download_link=log_file_url,
    )


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
    """Returns download links to log-files of each task in a computation.
    Each log is only available when the corresponding task is done
    """
    # gets computation task ids
    info = await analyze_pipeline(project_id, comp_pipelines_repo, comp_tasks_repo)
    iter_task_ids = (t.node_id for t in info.filtered_tasks)

    tasks_logs_files: list[TaskLogFileGet] = await logged_gather(
        *[
            _get_task_log_file(user_id, project_id, node_id)
            for node_id in iter_task_ids
        ],
        reraise=True,
        log=log,
    )
    return tasks_logs_files


@router.get(
    "/{project_id}/tasks/{node_uuid}/logfile",
    summary="Gets computation task logs file after is done",
    response_model=TaskLogFileGet,
)
async def get_task_log_file(
    user_id: UserID,
    project_id: ProjectID,
    node_uuid: NodeID,
    comp_tasks_repo: CompTasksRepository = Depends(get_repository(CompTasksRepository)),
) -> TaskLogFileGet:
    """Returns a link to download logs file of a give task.
    The log is only available when the task is done
    """

    if not await comp_tasks_repo.task_exists(project_id, node_uuid):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=[f"No task_id={node_uuid} found under computation {project_id}"],
        )

    return await _get_task_log_file(user_id, project_id, node_uuid)


# NOTE: This handler function is NOT ACTIVE
# but still kept as reference for future extensions that will tackle
# real-time log streaming (instead of logfile download)
#
# @router.get(
#    "/{project_id}/tasks/{node_uuid}/logs",
#    summary="Gets computation task log",
# )
# - Implement close as possible to https://docs.docker.com/engine/api/v1.41/#operation/ContainerTop
async def get_task_logs(
    user_id: UserID,
    project_id: ProjectID,
    node_uuid: NodeID,
) -> str:
    """Gets ``stdout`` and ``stderr`` logs from a computation task.
    It can return a list of the tail or stream live
    """

    raise NotImplementedError(f"/{project_id=}/tasks/{node_uuid=}/logs")
