import logging
from contextlib import contextmanager
from typing import Any, ClassVar, TypeAlias
from uuid import UUID

import httpx
from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from httpx import codes
from models_library.clusters import ClusterID
from models_library.projects_nodes import NodeID
from models_library.projects_pipeline import ComputationTask
from models_library.projects_state import RunningState
from pydantic import AnyHttpUrl, AnyUrl, BaseModel, Field, PositiveInt, parse_raw_as
from servicelib.error_codes import create_error_code
from servicelib.fastapi.httpx_utils import to_httpx_command
from simcore_service_api_server.db.repositories.groups_extra_properties import (
    GroupsExtraPropertiesRepository,
)
from starlette import status

from ..core.errors import DirectorError
from ..core.settings import DirectorV2Settings
from ..models.schemas.jobs import PercentageInt
from ..utils.client_base import BaseServiceClientApi, setup_client_instance

_logger = logging.getLogger(__name__)


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

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {
                    **ComputationTask.Config.schema_extra["examples"][0],
                    "url": "https://link-to-stop-computation",
                }
            ]
        }


class TaskLogFileGet(BaseModel):
    task_id: NodeID
    download_link: AnyUrl | None = Field(
        None, description="Presigned link for log file or None if still not available"
    )


NodeName: TypeAlias = str
DownloadLink: TypeAlias = AnyUrl


@contextmanager
def _handle_errors_context(project_id: UUID):
    try:
        yield

    except httpx.HTTPStatusError as err:
        if codes.is_client_error(err.response.status_code):
            if err.response.status_code == status.HTTP_404_NOT_FOUND:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Job {project_id} not found",
                ) from err

            # FIXME: what to do with these
            raise DirectorError.from_httpx_status_error(err) from err

        else:
            # server errors are logged and re-raised as 503
            assert codes.is_server_error(err.response.status_code)  # nosec

            oec = create_error_code(err)
            err_detail = (
                f"Service handling job '{project_id}' unexpectedly failed [{oec}]"
            )
            _logger.exception(
                "%s: %s",
                err_detail,
                DirectorError.from_httpx_status_error(err).get_debug_message(),
                extra={"error_code": oec},
            )

            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=err_detail,
            ) from err

    except httpx.TimeoutException as err:
        oec = create_error_code(err)
        err_detail = (
            f"Service handling job operation on '{project_id}' timed out [{oec}]"
        )
        _logger.exception(
            "%s: %s",
            err_detail,
            to_httpx_command(err.request),
            extra={"error_code": oec},
        )

        # SEE https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/504
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=err_detail,
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
        groups_extra_properties_repository: GroupsExtraPropertiesRepository,
        cluster_id: ClusterID | None = None,
    ) -> ComputationTaskGet:

        with _handle_errors_context(project_id):

            extras = {}

            use_on_demand_clusters = (
                await groups_extra_properties_repository.use_on_demand_clusters(
                    user_id, product_name
                )
            )

            if cluster_id is not None and not use_on_demand_clusters:
                extras["cluster_id"] = cluster_id

            response = await self.client.post(
                "/v2/computations",
                json={
                    "user_id": user_id,
                    "project_id": str(project_id),
                    "start_pipeline": True,
                    "product_name": product_name,
                    "use_on_demand_clusters": use_on_demand_clusters,
                    **extras,
                },
            )
            response.raise_for_status()
            return ComputationTaskGet(**response.json())

    async def get_computation(
        self, project_id: UUID, user_id: PositiveInt
    ) -> ComputationTaskGet:

        with _handle_errors_context(project_id):

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
        with _handle_errors_context(project_id):
            response = await self.client.post(
                f"/v2/computations/{project_id}:stop",
                json={
                    "user_id": user_id,
                },
            )

            return ComputationTaskGet(**response.json())

    async def delete_computation(self, project_id: UUID, user_id: PositiveInt):
        with _handle_errors_context(project_id):
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
        with _handle_errors_context(project_id):
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
