import logging
from contextlib import contextmanager
from typing import Optional
from uuid import UUID

from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from httpx import HTTPStatusError, codes
from models_library.projects_pipeline import ComputationTask
from models_library.projects_state import RunningState
from pydantic import AnyHttpUrl, Field, PositiveInt
from starlette import status

from ..core.settings import DirectorV2Settings
from ..models.schemas.jobs import PercentageInt
from ..utils.client_base import BaseServiceClientApi, setup_client_instance

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


# API CLASS ---------------------------------------------


@contextmanager
def handle_errors_context(project_id: UUID):
    try:

        yield

    # except ValidationError
    except HTTPStatusError as err:
        msg = (
            f"Failed {err.request.url} with status={err.response.status_code}: {err.response.json()}",
        )
        if codes.is_client_error(err.response.status_code):
            # client errors are mapped
            logger.debug(msg)
            if err.response.status_code == status.HTTP_404_NOT_FOUND:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Job {project_id} not found",
                ) from err

            raise err

        # server errors are logged and re-raised as 503
        assert codes.is_server_error(err.response.status_code)
        logger.exception(
            "director-v2 service failed: %s. Re-rasing as service unavailable (503)",
            msg,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Director service failed",
        ) from err


class DirectorV2Api(BaseServiceClientApi):
    # NOTE: keep here tmp as reference
    # @handle_errors("director", logger, return_json=True)
    # @handle_retry(logger)
    # async def get(self, path: str, *args, **kwargs) -> JSON:
    #     return await self.client.get(path, *args, **kwargs)

    # director2 API ---------------------------
    # TODO: error handling
    #
    #  HTTPStatusError: 404 Not Found
    #  ValidationError
    #  ServiceUnabalabe: 503

    async def create_computation(
        self, project_id: UUID, user_id: PositiveInt
    ) -> ComputationTaskOut:
        resp = await self.client.post(
            "/v2/computations",
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

        with handle_errors_context(project_id):
            resp = await self.client.post(
                "/v2/computations",
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
            f"/v2/computations/{project_id}",
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
            f"/v2/computations/{project_id}:stop",
            json={
                "user_id": user_id,
            },
        )

        computation_task = ComputationTaskOut(**data.json())
        return computation_task

    async def delete_computation(self, project_id: UUID, user_id: PositiveInt):
        await self.client.request(
            "DELETE",
            f"/v2/computations/{project_id}",
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
        app,
        DirectorV2Api,
        # WARNING: it has /v0 and /v2 prefixes
        api_baseurl=f"http://{settings.DIRECTOR_V2_HOST}:{settings.DIRECTOR_V2_PORT}",
        service_name="director_v2",
    )
