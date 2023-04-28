import json
import logging
from collections import deque
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from cryptography import fernet
from fastapi import FastAPI, HTTPException
from httpx import AsyncClient, Response
from models_library.projects import ProjectID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import ValidationError
from servicelib.aiohttp.long_running_tasks.server import TaskStatus
from starlette import status
from tenacity import TryAgain
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

from ..core.settings import WebServerSettings
from ..models.domain.projects import NewProjectIn, Project
from ..models.types import JSON, ListAnyDict
from ..utils.client_base import BaseServiceClientApi, setup_client_instance

_logger = logging.getLogger(__name__)


@dataclass
class AuthSession:
    """
    - wrapper around thin-client to simplify webserver's API
    - sets endspoint upon construction
    - MIME type: application/json
    - processes responses, returning data or raising formatted HTTP exception
    - The lifetime of an AuthSession is ONE request.

    SEE services/api-server/src/simcore_service_api_server/api/dependencies/webserver.py
    """

    client: AsyncClient  # Its lifetime is attached to app
    vtag: str
    session_cookies: dict | None = None

    @classmethod
    def create(cls, app: FastAPI, session_cookies: dict) -> "AuthSession":
        return cls(
            client=app.state.webserver_client,
            vtag=app.state.settings.API_SERVER_WEBSERVER.WEBSERVER_VTAG,
            session_cookies=session_cookies,
        )

    @classmethod
    def _postprocess(cls, resp: Response) -> JSON | None:
        # enveloped answer
        data: JSON | None = None
        error: JSON | None = None

        if resp.status_code != status.HTTP_204_NO_CONTENT:
            try:
                body = resp.json()
                data, error = body.get("data"), body.get("error")
            except json.JSONDecodeError:
                _logger.warning(
                    "Failed to unenvelop webserver response %s",
                    f"{resp.text=}",
                    exc_info=True,
                )

        if resp.is_server_error:
            _logger.error(
                "webserver error %s [%s]: %s",
                f"{resp.status_code=}",
                f"{resp.reason_phrase=}",
                error,
            )
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE)

        if resp.is_client_error:
            msg = error or resp.reason_phrase
            raise HTTPException(resp.status_code, detail=msg)

        return data

    # OPERATIONS

    async def get(self, path: str) -> JSON | None:
        url = path.lstrip("/")
        try:
            resp = await self.client.get(url, cookies=self.session_cookies)
        except Exception as err:
            _logger.exception("Failed to get %s", url)
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE) from err

        return self._postprocess(resp)

    async def put(self, path: str, body: dict) -> JSON | None:
        url = path.lstrip("/")
        try:
            resp = await self.client.put(url, json=body, cookies=self.session_cookies)
        except Exception as err:
            _logger.exception("Failed to put %s", url)
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE) from err

        return self._postprocess(resp)

    # PROJECTS resource ---

    async def create_project(self, project: NewProjectIn):
        # POST /projects --> 202
        resp = await self.client.post(
            "/projects",
            params={"hidden": True},
            json=jsonable_encoder(project, by_alias=True, exclude={"state"}),
            cookies=self.session_cookies,
        )
        data: JSON | None = self._postprocess(resp)
        assert data  # nosec
        assert isinstance(data, dict)  # nosec

        # NOTE: /v0 is already included in the http client base_url
        status_url = data["status_href"].lstrip(f"/{self.vtag}")
        result_url = data["result_href"].lstrip(f"/{self.vtag}")
        # GET task status now until done
        async for attempt in AsyncRetrying(
            wait=wait_fixed(0.5),
            stop=stop_after_delay(60),
            reraise=True,
            before_sleep=before_sleep_log(_logger, logging.INFO),
        ):
            with attempt:
                data = await self.get(status_url)
                task_status = TaskStatus.parse_obj(data)
                if not task_status.done:
                    raise TryAgain(
                        "Timed out creating project. TIP: Try again, or contact oSparc support if this is happening repeatedly"
                    )
        data = await self.get(f"{result_url}")
        return Project.parse_obj(data)

    async def get_project(self, project_id: UUID) -> Project:
        resp = await self.client.get(
            f"/projects/{project_id}", cookies=self.session_cookies
        )

        data: JSON | None = self._postprocess(resp)
        return Project.parse_obj(data)

    async def list_projects(self, solver_name: str) -> list[Project]:
        resp = await self.client.get(
            "/projects",
            params={"type": "user", "show_hidden": True},
            cookies=self.session_cookies,
        )

        data: ListAnyDict = cast(ListAnyDict, self._postprocess(resp)) or []

        projects: deque[Project] = deque()
        for prj in data:
            possible_job_name = prj.get("name", "")
            if possible_job_name.startswith(solver_name):
                try:
                    projects.append(Project.parse_obj(prj))
                except ValidationError as err:
                    _logger.warning(
                        "Invalid prj %s [%s]: %s", prj.get("uuid"), solver_name, err
                    )

        return list(projects)

    async def get_project_metadata_ports(
        self, project_id: ProjectID
    ) -> list[dict[str, Any]]:
        """
        maps GET "/projects/{study_id}/metadata/ports", unenvelopes
        and returns data
        """
        resp = await self.client.get(
            f"/projects/{project_id}/metadata/ports",
            cookies=self.session_cookies,
        )
        data = self._postprocess(resp)
        assert data
        assert isinstance(data, list)
        return data


class WebserverApi(BaseServiceClientApi):
    """Access to web-server API"""


# MODULES APP SETUP -------------------------------------------------------------


def setup(app: FastAPI, settings: WebServerSettings | None = None) -> None:
    if not settings:
        settings = WebServerSettings.create_from_envs()

    assert settings is not None  # nosec

    setup_client_instance(
        app, WebserverApi, api_baseurl=settings.api_base_url, service_name="webserver"
    )

    def on_startup() -> None:
        # normalize & encrypt
        secret_key = settings.WEBSERVER_SESSION_SECRET_KEY.get_secret_value()
        app.state.webserver_fernet = fernet.Fernet(secret_key)

        # init client
        _logger.debug("Setup webserver at %s...", settings.api_base_url)

        client = AsyncClient(base_url=settings.api_base_url)
        app.state.webserver_client = client

    async def on_shutdown() -> None:
        with suppress(AttributeError):
            client: AsyncClient = app.state.webserver_client
            await client.aclose()
            del app.state.webserver_client
        _logger.debug("Webserver closed successfully")

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
