""" CRUD operations on a computation's tasks sub-resource

A task is computation sub-resource that respresents a running computational service in the pipeline described above
Therefore,
 - the task ID is the same as the associated node uuid

"""
# pylint: disable=too-many-arguments


import logging

from fastapi import APIRouter
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from pydantic import AnyUrl, Field

from ...models.schemas.comp_tasks import BaseModel

log = logging.getLogger(__name__)

router = APIRouter()


class TaskLogFileGet(BaseModel):
    task_id: NodeID
    download_link: AnyUrl = Field(..., description="Donwload link for tasks' log file")


@router.get(
    "/{project_id}/tasks/-/logfile",
    summary="Gets computation task logs file after is done",
    response_model=list[TaskLogFileGet],
)
async def get_all_tasks_log_files(
    user_id: UserID, project_id: ProjectID, node_uuid: NodeID
) -> list[TaskLogFileGet]:
    """If a computation is done, it returns download links to log-files of each task in a computation"""
    raise NotImplementedError()


@router.get(
    "/{project_id}/tasks/{node_uuid}/logfile",
    summary="Gets computation task logs file after is done",
    response_model=TaskLogFileGet,
)
async def get_task_logs_file(
    user_id: UserID, project_id: ProjectID, node_uuid: NodeID
) -> TaskLogFileGet:
    """If a computation is done, it returns a link to download logs file of each task"""
    raise NotImplementedError()


@router.get(
    "/{project_id}/tasks/{node_uuid}/logs",
    summary="Gets computation task log",
)
async def get_task_logs(
    user_id: UserID, project_id: ProjectID, node_uuid: NodeID
) -> str:
    """Gets ``stdout`` and ``stderr`` logs from a computation task. It can return a list of the tail or stream live"""
    # TODO: as close as possible to https://docs.docker.com/engine/api/v1.41/#operation/ContainerTop
    raise NotImplementedError()
