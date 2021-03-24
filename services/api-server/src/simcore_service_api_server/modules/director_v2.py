import logging
from typing import List, Optional
from uuid import UUID

from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.projects_pipeline import ComputationTask
from pydantic import AnyHttpUrl, BaseModel, Field, PositiveInt

from ..core.settings import DirectorV2Settings

# from ..models.schemas.jobs import Job, JobInputs
from ..utils.client_base import BaseServiceClientApi, setup_client_instance
from ..utils.client_decorators import JsonDataType, handle_errors, handle_retry

logger = logging.getLogger(__name__)


# API MODELS ---------------------------------------------
# NOTE: as services/director-v2/src/simcore_service_director_v2/models/schemas/comp_tasks.py
# TODO: shall schemas of internal APIs be in models_library as well?? or is against

UserID = PositiveInt


class ComputationTaskOut(ComputationTask):
    url: AnyHttpUrl = Field(
        ..., description="the link where to get the status of the task"
    )
    stop_url: Optional[AnyHttpUrl] = Field(
        None, description="the link where to stop the task"
    )


class ComputationTaskCreate(BaseModel):
    user_id: UserID
    project_id: ProjectID
    start_pipeline: Optional[bool] = Field(
        False, description="if True the computation pipeline will start right away"
    )
    subgraph: Optional[List[NodeID]] = Field(
        None,
        description="An optional set of nodes that must be executed, if empty the whole pipeline is executed",
    )
    force_restart: Optional[bool] = Field(
        False, description="if True will force re-running all dependent nodes"
    )


class ComputationTaskStop(BaseModel):
    user_id: UserID


class ComputationTaskDelete(ComputationTaskStop):
    force: Optional[bool] = Field(
        False,
        description="if True then the pipeline will be removed even if it is running",
    )


# API CLASS ---------------------------------------------


class DirectorV2Api(BaseServiceClientApi):
    @handle_errors("director", logger, return_json=True)
    @handle_retry(logger)
    async def get(self, path: str, *args, **kwargs) -> JsonDataType:
        return await self.client.get(path, *args, **kwargs)

    # TODO: error handling

    async def create_computation(self, project_id: UUID, user_id: PositiveInt):
        data = await self.client.post(
            "/computations",
            json={
                "user_id": user_id,
                "project_id": project_id,
                "start_pipeline": False,
            },
        )

        _task = ComputationTaskOut(**data)


# MODULES APP SETUP -------------------------------------------------------------


def setup(app: FastAPI, settings: DirectorV2Settings) -> None:
    if not settings:
        settings = DirectorV2Settings()

    setup_client_instance(
        app, DirectorV2Api, api_baseurl=settings.base_url, service_name="director_v2"
    )
