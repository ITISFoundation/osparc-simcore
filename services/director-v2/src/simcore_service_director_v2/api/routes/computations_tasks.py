"""CRUD operations on a computation's tasks sub-resource

A task is computation sub-resource that respresents a running computational service in the pipeline described above
Therefore,
 - the task ID is the same as the associated node uuid

"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from models_library.api_schemas_directorv2.computations import (
    TaskLogFileGet,
    TasksOutputs,
    TasksSelection,
)
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from servicelib.utils import logged_gather
from starlette import status

from ...core.errors import PipelineTaskMissingError
from ...modules.db.repositories.comp_pipelines import CompPipelinesRepository
from ...modules.db.repositories.comp_tasks import CompTasksRepository
from ...utils import dask as dask_utils
from ...utils.computations_tasks import validate_pipeline
from ..dependencies.database import get_repository

log = logging.getLogger(__name__)

router = APIRouter()


# HELPERS -------------------------------------------------------------------


# ROUTES HANDLERS --------------------------------------------------------------


@router.get(
    "/{project_id}/tasks/-/logfile",
    summary="Gets computation task logs file after is done",
    response_model=list[TaskLogFileGet],
)
async def get_all_tasks_log_files(
    user_id: UserID,
    project_id: ProjectID,
    comp_pipelines_repo: Annotated[
        CompPipelinesRepository, Depends(get_repository(CompPipelinesRepository))
    ],
    comp_tasks_repo: Annotated[
        CompTasksRepository, Depends(get_repository(CompTasksRepository))
    ],
) -> list[TaskLogFileGet]:
    """Returns download links to log-files of each task in a computation.
    Each log is only available when the corresponding task is done
    """
    # gets computation task ids
    try:
        info = await validate_pipeline(project_id, comp_pipelines_repo, comp_tasks_repo)
    except PipelineTaskMissingError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The tasks referenced by the pipeline are missing",
        ) from exc
    iter_task_ids = (t.node_id for t in info.filtered_tasks)

    tasks_logs_files: list[TaskLogFileGet] = await logged_gather(
        *[
            dask_utils.get_task_log_file(user_id, project_id, node_id)
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
    comp_tasks_repo: Annotated[
        CompTasksRepository, Depends(get_repository(CompTasksRepository))
    ],
) -> TaskLogFileGet:
    """Returns a link to download logs file of a give task.
    The log is only available when the task is done
    """

    if not await comp_tasks_repo.task_exists(project_id, node_uuid):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=[f"No task_id={node_uuid} found under computation {project_id}"],
        )

    return await dask_utils.get_task_log_file(user_id, project_id, node_uuid)


@router.post(
    "/{project_id}/tasks/-/outputs:batchGet",
    summary="Gets all outputs for selected tasks",
    response_model=TasksOutputs,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Cannot find computation or the tasks in it"
        }
    },
)
async def get_batch_tasks_outputs(
    project_id: ProjectID,
    selection: TasksSelection,
    comp_tasks_repo: Annotated[
        CompTasksRepository, Depends(get_repository(CompTasksRepository))
    ],
):
    nodes_outputs = await comp_tasks_repo.get_outputs_from_tasks(
        project_id, set(selection.nodes_ids)
    )

    if not nodes_outputs:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    return TasksOutputs(nodes_outputs=nodes_outputs)
