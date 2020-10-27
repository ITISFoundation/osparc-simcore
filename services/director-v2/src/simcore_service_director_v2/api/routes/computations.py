from fastapi import APIRouter, Depends
from uuid import UUID
from pydantic.types import PositiveInt

from ...modules.celery import CeleryClient
from ...modules.db.repositories.computations import (
    CompPipelinesRepository,
    CompTasksRepository,
)
from ...modules.db.repositories.projects import ProjectsRepository
from ..dependencies.celery import get_celery_client
from ..dependencies.database import get_repository

router = APIRouter()

UserId = PositiveInt
ProjectId = UUID


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
    project_id: ProjectId,
    project_repo: ProjectsRepository = Depends(get_repository(ProjectsRepository)),
    celery_client: CeleryClient = Depends(get_celery_client),
):
    project_repo = await project_repo.get_project(str(project_id))

    # get the state
    # return forbidden if the state is not ok
    # update the pipeline
    # start the pipeline
    # return the project/id, task id or else failed to start


@router.get("/{computation_id}")
async def get_computation(computation_id: ProjectId):
    pass


@router.delete("/{computation_id}", description="Stops a computation")
async def stop_computation(computation_id: ProjectId):
    pass
