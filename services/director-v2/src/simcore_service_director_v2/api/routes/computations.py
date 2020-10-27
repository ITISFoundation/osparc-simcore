from typing import Dict

from fastapi import APIRouter, Depends
from models_library.projects import NodeID, ProjectID
from pydantic.types import PositiveInt

from ...models.domains.comp_tasks import CompTaskAtDB
from ...modules.db.repositories.computations import (
    CompPipelinesRepository,
    CompTasksRepository,
)
from ...modules.db.repositories.projects import ProjectsRepository
from ..dependencies.celery import CeleryApp
from ..dependencies.database import get_repository
from ..dependencies.director_v0 import DirectorClient

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
    director_client: DirectorClient = Depends(),
):
    project_repo = await project_repo.get_project(project_id)
    task_states: Dict[NodeID, CompTaskAtDB] = await computation_tasks.get_comp_tasks(
        project_id
    )
    return task_states

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
