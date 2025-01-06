"""Module that takes care of communications with director v0 service"""

import logging
import urllib.parse
from dataclasses import dataclass
from typing import Any, cast

import httpx
import yarl
from fastapi import FastAPI, HTTPException, status
from models_library.api_schemas_directorv2.dynamic_services_service import (
    RunningDynamicServiceDetails,
)
from models_library.api_schemas_directorv2.services import ServiceExtras
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.service_settings_labels import SimcoreServiceLabels
from models_library.services import ServiceKey, ServiceKeyVersion, ServiceVersion
from models_library.users import UserID
from servicelib.fastapi.tracing import setup_httpx_client_tracing
from servicelib.logging_utils import log_decorator
from settings_library.tracing import TracingSettings

from ..core.settings import DirectorV0Settings
from ..utils.client_decorators import handle_errors, handle_retry
from ..utils.clients import unenvelope_or_raise_error

logger = logging.getLogger(__name__)

# Module's setup logic ---------------------------------------------


def setup(
    app: FastAPI,
    director_v0_settings: DirectorV0Settings | None,
    tracing_settings: TracingSettings | None,
):
    if not director_v0_settings:
        director_v0_settings = DirectorV0Settings()

    def on_startup() -> None:
        client = httpx.AsyncClient(
            base_url=f"{director_v0_settings.endpoint}",
            timeout=app.state.settings.CLIENT_REQUEST.HTTP_CLIENT_REQUEST_TOTAL_TIMEOUT,
        )
        if tracing_settings:
            setup_httpx_client_tracing(client=client)
        DirectorV0Client.create(
            app,
            client=client,
        )
        logger.debug(
            "created client for director-v0: %s", director_v0_settings.endpoint
        )

    async def on_shutdown() -> None:
        client = DirectorV0Client.instance(app).client
        await client.aclose()
        del client
        logger.debug("delete client for director-v0: %s", director_v0_settings.endpoint)

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


@dataclass
class DirectorV0Client:
    client: httpx.AsyncClient

    @classmethod
    def create(cls, app: FastAPI, **kwargs) -> "DirectorV0Client":
        app.state.director_v0_client = cls(**kwargs)
        return cls.instance(app)

    @classmethod
    def instance(cls, app: FastAPI) -> "DirectorV0Client":
        client: DirectorV0Client = app.state.director_v0_client
        return client

    @handle_errors("Director", logger)
    @handle_retry(logger)
    async def _request(self, method: str, tail_path: str, **kwargs) -> httpx.Response:
        return await self.client.request(method, tail_path, **kwargs)

    @log_decorator(logger=logger)
    async def get_service_extras(
        self, service_key: ServiceKey, service_version: ServiceVersion
    ) -> ServiceExtras:
        resp = await self._request(
            "GET",
            f"/service_extras/{urllib.parse.quote_plus(service_key)}/{service_version}",
        )
        if resp.status_code == status.HTTP_200_OK:
            return ServiceExtras.model_validate(unenvelope_or_raise_error(resp))
        raise HTTPException(status_code=resp.status_code, detail=resp.content)

    @log_decorator(logger=logger)
    async def get_running_service_details(
        self, service_uuid: NodeID
    ) -> RunningDynamicServiceDetails:
        resp = await self._request(
            "GET", f"running_interactive_services/{service_uuid}"
        )
        if resp.status_code == status.HTTP_200_OK:
            return RunningDynamicServiceDetails.model_validate(
                unenvelope_or_raise_error(resp)
            )
        raise HTTPException(status_code=resp.status_code, detail=resp.content)

    @log_decorator(logger=logger)
    async def get_service_labels(
        self, service: ServiceKeyVersion
    ) -> SimcoreServiceLabels:
        resp = await self._request(
            "GET",
            f"services/{urllib.parse.quote_plus(service.key)}/{service.version}/labels",
        )
        resp.raise_for_status()
        if resp.status_code == status.HTTP_200_OK:
            return SimcoreServiceLabels.model_validate(unenvelope_or_raise_error(resp))
        raise HTTPException(status_code=resp.status_code, detail=resp.content)

    @log_decorator(logger=logger)
    async def get_running_services(
        self, user_id: UserID | None = None, project_id: ProjectID | None = None
    ) -> list[RunningDynamicServiceDetails]:
        query_params = {}
        if user_id is not None:
            query_params["user_id"] = f"{user_id}"
        if project_id is not None:
            query_params["study_id"] = f"{project_id}"
        request_url = yarl.URL("running_interactive_services").with_query(query_params)

        resp = await self._request("GET", str(request_url))
        resp.raise_for_status()

        if resp.status_code == status.HTTP_200_OK:
            return [
                RunningDynamicServiceDetails(**x)
                for x in cast(list[dict[str, Any]], unenvelope_or_raise_error(resp))
            ]
        raise HTTPException(status_code=resp.status_code, detail=resp.content)
