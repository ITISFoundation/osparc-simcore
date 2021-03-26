import logging
from datetime import datetime
from typing import Optional, Type
from uuid import UUID

from fastapi import FastAPI
from models_library.projects_pipeline import ComputationTask
from models_library.projects_state import RunningState
from pydantic import AnyHttpUrl, Field, PositiveInt, conint

from ..core.settings import DirectorV2Settings
from ..models.schemas.jobs import JobStatus, TaskStates
from ..utils.client_base import BaseServiceClientApi, setup_client_instance
from ..utils.client_decorators import JsonDataType, handle_errors, handle_retry
from ..utils.serialization import json_dumps

PercentageInt: Type[int] = conint(ge=0, le=100)


logger = logging.getLogger(__name__)


# API MODELS ---------------------------------------------
# NOTE: as services/director-v2/src/simcore_service_director_v2/models/schemas/comp_tasks.py
# TODO: shall schemas of internal APIs be in models_library as well?? or is against


class ComputationTaskOut(ComputationTask):
    url: AnyHttpUrl = Field(
        ..., description="the link where to get the status of the task"
    )
    stop_url: Optional[AnyHttpUrl] = Field(
        None, description="the link where to stop the task"
    )

    def guess_progress(self) -> PercentageInt:
        # guess progress based on self.state
        # FIXME: incomplete!
        if self.state in [RunningState.SUCCESS, RunningState.FAILED]:
            return 100
        return 0

    def as_jobstatus(self) -> JobStatus:
        """ Creates a JobStatus instance out of this task """
        job_status = JobStatus(
            job_id=self.id,
            state=self.state,
            progress=self.guess_progress(),
            submitted_at=datetime.utcnow(),
        )

        # FIXME: timestamp is wrong but at least it will stop run
        if job_status.state in [
            TaskStates.SUCCESS,
            TaskStates.FAILED,
            TaskStates.ABORTED,
        ]:
            job_status.take_snapshot("stopped")
        elif job_status.state in [
            TaskStates.STARTED,
        ]:
            job_status.take_snapshot("started")

        return job_status


# API CLASS ---------------------------------------------


class DirectorV2Api(BaseServiceClientApi):
    @handle_errors("director", logger, return_json=True)
    @handle_retry(logger)
    async def get(self, path: str, *args, **kwargs) -> JsonDataType:
        return await self.client.get(path, *args, **kwargs)

    # director2 API ---------------------------
    # TODO: error handling
    #
    #  HTTPStatusError: 404 Not Found
    #  ValidationError
    #

    async def create_computation(
        self, project_id: UUID, user_id: PositiveInt
    ) -> ComputationTaskOut:
        resp = await self.client.post(
            "/computations",
            json={
                "user_id": user_id,
                "project_id": str(project_id),
                "start_pipeline": False,
            },
        )

        resp.raise_for_status()
        computation_task = ComputationTaskOut(**resp.json())
        return computation_task

    async def start_computation(
        self, project_id: UUID, user_id: PositiveInt
    ) -> ComputationTaskOut:
        resp = await self.client.post(
            "/computations",
            json={
                "user_id": user_id,
                "project_id": str(project_id),
                "start_pipeline": True,
            },
        )
        resp.raise_for_status()
        computation_task = ComputationTaskOut(**resp.json())
        return computation_task

    async def get_computation(
        self, project_id: UUID, user_id: PositiveInt
    ) -> ComputationTaskOut:
        resp = await self.client.get(
            f"/computations/{project_id}",
            params={
                "user_id": user_id,
            },
        )
        resp.raise_for_status()
        computation_task = ComputationTaskOut(**resp.json())
        return computation_task

    async def stop_computation(
        self, project_id: UUID, user_id: PositiveInt
    ) -> ComputationTaskOut:
        data = await self.client.post(
            f"/computations/{project_id}:stop",
            json={
                "user_id": user_id,
            },
        )

        computation_task = ComputationTaskOut(**data.json())
        return computation_task

    async def delete_computation(self, project_id: UUID, user_id: PositiveInt):
        await self.client.request(
            "DELETE",
            f"/computations/{project_id}",
            json={
                "user_id": user_id,
                "force": True,
            },
        )

    # TODO: HIGHER lever interface with job* resources
    # or better in another place?
    async def create_job(self):
        pass

    async def list_jobs(self):
        pass

    async def get_job(self):
        pass


# MODULES APP SETUP -------------------------------------------------------------


def setup(app: FastAPI, settings: DirectorV2Settings) -> None:
    if not settings:
        settings = DirectorV2Settings()

    setup_client_instance(
        app, DirectorV2Api, api_baseurl=settings.base_url, service_name="director_v2"
    )
