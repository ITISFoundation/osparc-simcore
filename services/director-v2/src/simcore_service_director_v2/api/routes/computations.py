from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from models_library.projects import NodeID, ProjectID, RunningState
from pydantic.types import PositiveInt
from starlette import status

from ...models.domains.comp_tasks import CompTaskAtDB
from ...modules.db.repositories.computations import (
    CompPipelinesRepository,
    CompTasksRepository,
)
from ...modules.db.repositories.projects import ProjectsRepository
from ...utils.computations import get_pipeline_state_from_task_states
from ..dependencies.celery import CeleryApp
from ..dependencies.database import get_repository
from ..dependencies.director_v0 import DirectorV0Client, get_director_v0_client

router = APIRouter()

UserId = PositiveInt


@router.get("")
async def list_computations(
    user_id: UserId,
    computation_pipelines: CompPipelinesRepository = Depends(
        get_repository(CompPipelinesRepository)
    ),
    computation_tasks: CompTasksRepository = Depends(
        get_repository(CompTasksRepository)
    ),
):
    pass


@router.post("", description="Create and Start a new computation")
async def create_computation(
    user_id: UserId,
    project_id: ProjectID,
    project_repo: ProjectsRepository = Depends(get_repository(ProjectsRepository)),
    computation_tasks: CompTasksRepository = Depends(
        get_repository(CompTasksRepository)
    ),
    celery_client: CeleryApp = Depends(),
    director_client: DirectorV0Client = Depends(get_director_v0_client),
):
    project_repo = await project_repo.get_project(project_id)
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
            detail=f"Projet {project_id} already started, state {pipeline_state}",
        )
    return pipeline_state

    # get the state
    # return forbidden if the state is not ok
    # update the pipeline
    # start the pipeline
    # return the project/id, task id or else failed to start


@router.get("/{computation_id}")
async def get_computation(computation_id: ProjectID):
    pass


@router.delete("/{computation_id}", description="Stops a computation")
async def stop_computation(computation_id: ProjectID):
    pass
