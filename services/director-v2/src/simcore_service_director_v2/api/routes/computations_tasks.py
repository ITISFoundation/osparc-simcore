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
from starlette import status

from ...models.schemas.comp_tasks import TaskLogGet

log = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/{project_id}/tasks/{node_uuid}/logs",
    summary="Gets computation task log",
    response_model=TaskLogGet,
    status_code=status.HTTP_200_OK,
)
async def get_computation_task_logs(
    user_id: UserID, project_id: ProjectID, node_uuid: NodeID
) -> TaskLogGet:
    """Gets ``stdout`` and ``stderr`` logs from a computation task"""
    # TODO: as close as possible to https://docs.docker.com/engine/api/v1.41/#operation/ContainerTop
    raise NotImplementedError()
