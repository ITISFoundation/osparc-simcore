import logging
from contextlib import contextmanager
from uuid import UUID

from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from httpx import HTTPStatusError, codes
from models_library.clusters import ClusterID
from models_library.projects_nodes import NodeID
from models_library.projects_pipeline import ComputationTask
from models_library.projects_state import RunningState
from pydantic import AnyHttpUrl, AnyUrl, BaseModel, Field, PositiveInt, parse_raw_as
from starlette import status

from ..core.settings import DirectorV2Settings
from ..models.schemas.jobs import PercentageInt
from ..utils.client_base import BaseServiceClientApi, setup_client_instance

logger = logging.getLogger(__name__)


# API MODELS ---------------------------------------------
# NOTE: as services/director-v2/src/simcore_service_director_v2/models/schemas/comp_tasks.py


class ComputationTaskGet(ComputationTask):
    url: AnyHttpUrl = Field(
        ..., description="the link where to get the status of the task"
    )
    stop_url: AnyHttpUrl | None = Field(
        None, description="the link where to stop the task"
    )

    def guess_progress(self) -> PercentageInt:
        # guess progress based on self.state
        if self.state in [RunningState.SUCCESS, RunningState.FAILED]:
            return PercentageInt(100)
        return PercentageInt(0)


class TaskLogFileGet(BaseModel):
    task_id: NodeID
    download_link: AnyUrl | None = Field(
        None, description="Presigned link for log file or None if still not available"
    )


NodeName = str
DownloadLink = AnyUrl

# API CLASS ---------------------------------------------


@contextmanager
def _handle_errors_context(project_id: UUID):
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
        assert codes.is_server_error(err.response.status_code)  # nosec

        logger.exception(
            "director-v2 service failed: %s. Re-rasing as service unavailable (503)",
            msg,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Director service failed",
        ) from err


class DirectorV2Api(BaseServiceClientApi):
    async def create_computation(
        self,
        project_id: UUID,
        user_id: PositiveInt,
        product_name: str,
    ) -> ComputationTaskGet:
        response = await self.client.post(
            "/v2/computations",
            json={
                "user_id": user_id,
                "project_id": str(project_id),
                "start_pipeline": False,
                "product_name": product_name,
            },
        )
        response.raise_for_status()
        return ComputationTaskGet(**response.json())

    async def start_computation(
        self,
        project_id: UUID,
        user_id: PositiveInt,
        product_name: str,
        cluster_id: ClusterID | None = None,
    ) -> ComputationTaskGet:
        with _handle_errors_context(project_id):
            extras = {}
            if cluster_id is not None:
                extras["cluster_id"] = cluster_id

            response = await self.client.post(
                "/v2/computations",
                json={
                    "user_id": user_id,
                    "project_id": str(project_id),
                    "start_pipeline": True,
                    "product_name": product_name,
                    **extras,
                },
            )
            response.raise_for_status()
            return ComputationTaskGet(**response.json())

    async def get_computation(
        self, project_id: UUID, user_id: PositiveInt
    ) -> ComputationTaskGet:
        response = await self.client.get(
            f"/v2/computations/{project_id}",
            params={
                "user_id": user_id,
            },
        )
        response.raise_for_status()
        return ComputationTaskGet(**response.json())

    async def stop_computation(
        self, project_id: UUID, user_id: PositiveInt
    ) -> ComputationTaskGet:
        response = await self.client.post(
            f"/v2/computations/{project_id}:stop",
            json={
                "user_id": user_id,
            },
        )

        return ComputationTaskGet(**response.json())

    async def delete_computation(self, project_id: UUID, user_id: PositiveInt):
        await self.client.request(
            "DELETE",
            f"/v2/computations/{project_id}",
            json={
                "user_id": user_id,
                "force": True,
            },
        )

    async def get_computation_logs(
        self, user_id: PositiveInt, project_id: UUID
    ) -> dict[NodeName, DownloadLink]:
        response = await self.client.get(
            f"/v2/computations/{project_id}/tasks/-/logfile",
            params={
                "user_id": user_id,
            },
        )

        # probably not found
        response.raise_for_status()

        node_to_links: dict[NodeName, DownloadLink] = {}
        for r in parse_raw_as(list[TaskLogFileGet], response.text or "[]"):
            if r.download_link:
                node_to_links[f"{r.task_id}"] = r.download_link

        return node_to_links


# MODULES APP SETUP -------------------------------------------------------------


def setup(app: FastAPI, settings: DirectorV2Settings) -> None:
    if not settings:
        settings = DirectorV2Settings()

    setup_client_instance(
        app,
        DirectorV2Api,
        # WARNING: it has /v0 and /v2 prefixes
        api_baseurl=settings.base_url,
        service_name="director_v2",
    )
