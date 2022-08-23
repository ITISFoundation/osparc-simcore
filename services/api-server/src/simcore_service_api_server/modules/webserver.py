import base64
import json
import logging
from collections import deque
from contextlib import suppress
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from cryptography import fernet
from fastapi import FastAPI, HTTPException
from httpx import AsyncClient, Response
from pydantic import ValidationError
from starlette import status

from ..core.settings import WebServerSettings
from ..models.domain.projects import NewProjectIn, Project
from ..models.raw_data import JSON, ListAnyDict
from ..utils.client_base import BaseServiceClientApi, setup_client_instance

logger = logging.getLogger(__name__)


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
    session_cookies: Optional[dict] = None

    @classmethod
    def create(cls, app: FastAPI, session_cookies: dict):
        return cls(
            client=app.state.webserver_client,
            vtag=app.state.settings.API_SERVER_WEBSERVER.WEBSERVER_VTAG,
            session_cookies=session_cookies,
        )

    @classmethod
    def _process(cls, resp: Response) -> Optional[JSON]:
        # enveloped answer
        data, error = None, None

        if resp.status_code != status.HTTP_204_NO_CONTENT:
            try:
                body = resp.json()
                data, error = body.get("data"), body.get("error")
            except json.JSONDecodeError:
                logger.warning(
                    "Failed to unenvelop webserver response %s",
                    f"{resp.text=}",
                    exc_info=True,
                )

        if resp.is_server_error:
            logger.error(
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
    # TODO: refactor and code below
    # TODO: policy to retry if NetworkError/timeout?
    # TODO: add ping to healthcheck

    async def get(self, path: str) -> Optional[JSON]:
        url = path.lstrip("/")
        try:
            resp = await self.client.get(url, cookies=self.session_cookies)
        except Exception as err:
            # FIXME: error handling
            logger.exception("Failed to get %s", url)
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE) from err

        return self._process(resp)

    async def put(self, path: str, body: dict) -> Optional[JSON]:
        url = path.lstrip("/")
        try:
            resp = await self.client.put(url, json=body, cookies=self.session_cookies)
        except Exception as err:
            logger.exception("Failed to put %s", url)
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE) from err

        return self._process(resp)

    # PROJECTS resource ---
    # TODO: error handling!

    async def create_project(self, project: NewProjectIn):
        resp = await self.client.post(
            "/projects",
            params={"hidden": True},
            data=project.json(
                by_alias=True, exclude={"state"}
            ),  ## FIXME: REEAAAALY HACKY!
            cookies=self.session_cookies,
        )

        data: Optional[JSON] = self._process(resp)
        return Project.parse_obj(data)

    async def get_project(self, project_id: UUID) -> Project:
        resp = await self.client.get(
            f"/projects/{project_id}", cookies=self.session_cookies
        )

        data: Optional[JSON] = self._process(resp)
        return Project.parse_obj(data)

    async def list_projects(self, solver_name: str) -> list[Project]:
        # TODO: pagination?
        resp = await self.client.get(
            "/projects",
            params={"type": "user", "show_hidden": True},
            cookies=self.session_cookies,
        )

        data: ListAnyDict = self._process(resp) or []

        # FIXME: move filter to webserver API (next PR)
        projects: deque[Project] = deque()
        for prj in data:
            possible_job_name = prj.get("name", "")
            if possible_job_name.startswith(solver_name):
                try:
                    projects.append(Project.parse_obj(prj))
                except ValidationError as err:
                    logger.warning(
                        "Invalid prj %s [%s]: %s", prj.get("uuid"), solver_name, err
                    )

        return list(projects)


def _get_secret_key(settings: WebServerSettings):
    secret_key_bytes = settings.WEBSERVER_SESSION_SECRET_KEY.get_secret_value().encode(
        "utf-8"
    )
    while len(secret_key_bytes) < 32:
        secret_key_bytes += secret_key_bytes
    secret_key = secret_key_bytes[:32]

    if isinstance(secret_key, str):
        pass
    elif isinstance(secret_key, (bytes, bytearray)):
        secret_key = base64.urlsafe_b64encode(secret_key)
    return secret_key


class WebserverApi(BaseServiceClientApi):
    """Access to web-server API"""

    # def create_auth_session(self, session_cookies) -> AuthSession:
    #     """ Needed per request, so it can perform """
    #     return AuthSession(client=self.client, vtag="v0", session_cookies=session_cookies)


# MODULES APP SETUP -------------------------------------------------------------


def setup(app: FastAPI, settings: Optional[WebServerSettings] = None) -> None:
    if not settings:
        settings = WebServerSettings()

    assert settings is not None  # nosec

    setup_client_instance(
        app, WebserverApi, api_baseurl=settings.base_url, service_name="webserver"
    )

    # TODO: old startup. need to integrat
    # TODO: init client and then build sessions from client using depenencies

    def on_startup() -> None:
        # normalize & encrypt
        secret_key = settings.WEBSERVER_SESSION_SECRET_KEY.get_secret_value()
        app.state.webserver_fernet = fernet.Fernet(secret_key)

        # init client
        logger.debug("Setup webserver at %s...", settings.base_url)

        client = AsyncClient(base_url=settings.base_url)
        app.state.webserver_client = client

    async def on_shutdown() -> None:
        with suppress(AttributeError):
            client: AsyncClient = app.state.webserver_client
            await client.aclose()
            del app.state.webserver_client
        logger.debug("Webserver closed successfully")

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
