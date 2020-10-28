from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from models_library.projects import NodeID, ProjectID, RunningState
from pydantic.main import BaseModel
from pydantic.types import PositiveInt
from simcore_service_director_v2.utils.exceptions import ProjectNotFoundError
from starlette import status

from ...models.domains.comp_tasks import CompTaskAtDB
from ...models.schemas.constants import UserID
from ...modules.db.repositories.computations import (
    CompPipelinesRepository,
    CompTasksRepository,
)
from ...modules.db.repositories.projects import ProjectsRepository
from ...utils.computations import get_pipeline_state_from_task_states
from ..dependencies.celery import CeleryClient, get_celery_client
from ..dependencies.database import get_repository
from ..dependencies.director_v0 import DirectorV0Client, get_director_v0_client

router = APIRouter()


@router.get("")
async def list_computations(
    user_id: UserID,
    computation_pipelines: CompPipelinesRepository = Depends(
        get_repository(CompPipelinesRepository)
    ),
    computation_tasks: CompTasksRepository = Depends(
        get_repository(CompTasksRepository)
    ),
):
    pass


from uuid import UUID


class ComputationTask(BaseModel):
    id: UUID


@router.post(
    "", description="Create and Start a new computation", response_model=ComputationTask
)
async def create_computation(
    user_id: UserID,
    project_id: ProjectID,
    project_repo: ProjectsRepository = Depends(get_repository(ProjectsRepository)),
    computation_tasks: CompTasksRepository = Depends(
        get_repository(CompTasksRepository)
    ),
    celery_client: CeleryClient = Depends(get_celery_client),
    director_client: DirectorV0Client = Depends(get_director_v0_client),
):
    try:
        # get the project
        await project_repo.get_project(project_id)

        # check the current state is startable
        comp_tasks: Dict[NodeID, CompTaskAtDB] = await computation_tasks.get_comp_tasks(
            project_id
        )
        pipeline_state = get_pipeline_state_from_task_states(comp_tasks)
        if pipeline_state in [
            RunningState.PUBLISHED,
            RunningState.PENDING,
            RunningState.STARTED,
            RunningState.RETRY,
        ]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Projet {project_id} already started, current state is {pipeline_state}",
            )

        # ok so publish the tasks
        await computation_tasks.publish_tasks(project_id)
        # trigger celery
        async_result = celery_client.send_computation_task(user_id, project_id)
        return ComputationTask(id=async_result.id)

    except ProjectNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get("/{computation_id}")
async def get_computation(computation_id: ProjectID):
    pass


@router.delete("/{computation_id}", description="Stops a computation")
async def stop_computation(computation_id: ProjectID):
    pass
