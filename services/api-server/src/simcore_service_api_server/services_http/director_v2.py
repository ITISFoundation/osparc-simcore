import logging
from functools import partial
from uuid import UUID

from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from models_library.projects_pipeline import ComputationTask
from models_library.projects_state import RunningState
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, PositiveInt, TypeAdapter
from pydantic.config import JsonDict
from settings_library.tracing import TracingSettings
from starlette import status

from ..core.settings import DirectorV2Settings
from ..exceptions.backend_errors import JobNotFoundError, LogFileNotFoundError
from ..exceptions.service_errors_utils import service_exception_mapper
from ..models.schemas.jobs import PercentageInt
from ..models.schemas.studies import JobLogsMap, LogLink
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
            return 100
        return 0

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        **ComputationTask.model_json_schema()["examples"][0],  # type: ignore
                        "url": "https://link-to-stop-computation",
                    }
                ]
            }
        )

    model_config = ConfigDict(
        json_schema_extra=_update_json_schema_extra,
    )


class TaskLogFileGet(BaseModel):
    task_id: NodeID
    download_link: AnyHttpUrl | None = Field(
        None, description="Presigned link for log file or None if still not available"
    )


# API CLASS ---------------------------------------------

_exception_mapper = partial(service_exception_mapper, service_name="Director V2")


class DirectorV2Api(BaseServiceClientApi):

    @_exception_mapper(http_status_map={status.HTTP_404_NOT_FOUND: JobNotFoundError})
    async def get_computation(
        self, *, project_id: UUID, user_id: PositiveInt
    ) -> ComputationTaskGet:
        response = await self.client.get(
            f"/v2/computations/{project_id}",
            params={
                "user_id": user_id,
            },
        )
        response.raise_for_status()
        task: ComputationTaskGet = ComputationTaskGet.model_validate_json(response.text)
        return task

    @_exception_mapper(http_status_map={status.HTTP_404_NOT_FOUND: JobNotFoundError})
    async def stop_computation(
        self, *, project_id: UUID, user_id: PositiveInt
    ) -> ComputationTaskGet:
        response = await self.client.post(
            f"/v2/computations/{project_id}:stop",
            json={
                "user_id": user_id,
            },
        )
        response.raise_for_status()
        task: ComputationTaskGet = ComputationTaskGet.model_validate_json(response.text)
        return task

    @_exception_mapper(http_status_map={status.HTTP_404_NOT_FOUND: JobNotFoundError})
    async def delete_computation(self, *, project_id: UUID, user_id: PositiveInt):
        response = await self.client.request(
            "DELETE",
            f"/v2/computations/{project_id}",
            json={
                "user_id": user_id,
                "force": True,
            },
        )
        response.raise_for_status()

    @_exception_mapper(
        http_status_map={status.HTTP_404_NOT_FOUND: LogFileNotFoundError}
    )
    async def get_computation_logs(
        self, *, user_id: PositiveInt, project_id: UUID
    ) -> JobLogsMap:
        response = await self.client.get(
            f"/v2/computations/{project_id}/tasks/-/logfile",
            params={
                "user_id": user_id,
            },
        )

        # probably not found
        response.raise_for_status()

        log_links: list[LogLink] = [
            LogLink(node_name=f"{r.task_id}", download_link=r.download_link)
            for r in TypeAdapter(list[TaskLogFileGet]).validate_json(
                response.text or "[]"
            )
            if r.download_link
        ]

        return JobLogsMap(log_links=log_links)


# MODULES APP SETUP -------------------------------------------------------------


def setup(
    app: FastAPI, settings: DirectorV2Settings, tracing_settings: TracingSettings | None
) -> None:
    setup_client_instance(
        app,
        DirectorV2Api,
        # WARNING: it has /v0 and /v2 prefixes
        api_baseurl=settings.base_url,
        service_name="director_v2",
        tracing_settings=tracing_settings,
    )
