import base64
import json
import logging
from collections import deque
from contextlib import suppress
from typing import Deque, Dict, List, Optional
from uuid import UUID

import attr
from cryptography import fernet
from fastapi import FastAPI, HTTPException
from httpx import AsyncClient, Response, codes
from pydantic import ValidationError
from starlette import status

from ..core.settings import WebServerSettings
from ..models.domain.projects import NewProjectIn, Project
from ..models.raw_data import JSON, ListAnyDict

logger = logging.getLogger(__name__)


# Module's setup logic ---------------------------------------------


def setup(app: FastAPI, settings: Optional[WebServerSettings] = None) -> None:
    if not settings:
        settings = WebServerSettings()

    def on_startup() -> None:
        # normalize & encrypt
        secret_key = _get_secret_key(settings)
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


# Module's business logic ---------------------------------------------


def _get_secret_key(settings: WebServerSettings):
    secret_key_bytes = settings.session_secret_key.get_secret_value().encode("utf-8")
    while len(secret_key_bytes) < 32:
        secret_key_bytes += secret_key_bytes
    secret_key = secret_key_bytes[:32]

    if isinstance(secret_key, str):
        pass
    elif isinstance(secret_key, (bytes, bytearray)):
        secret_key = base64.urlsafe_b64encode(secret_key)
    return secret_key


@attr.s(auto_attribs=True)
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
    session_cookies: Dict = None

    @classmethod
    def create(cls, app: FastAPI, session_cookies: Dict):
        return cls(
            client=app.state.webserver_client,
            vtag=app.state.settings.webserver.vtag,
            session_cookies=session_cookies,
        )

    @classmethod
    def _process(cls, resp: Response) -> Optional[JSON]:
        # enveloped answer
        data, error = None, None
        try:
            body = resp.json()
            data, error = body.get("data"), body.get("error")
        except (json.JSONDecodeError, KeyError):
            logger.warning("Failed to unenvelop webserver response", exc_info=True)

        if codes.is_server_error(resp.status_code):
            logger.error(
                "webserver error %d [%s]: %s",
                resp.status_code,
                resp.reason_phrase,
                error,
            )
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE)

        if codes.is_client_error(resp.status_code):
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

    async def put(self, path: str, body: Dict) -> Optional[JSON]:
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

    async def list_projects(self, solver_name: str) -> List[Project]:
        resp = await self.client.get(
            "/projects", params={"type": "user"}, cookies=self.session_cookies
        )

        data: ListAnyDict = self._process(resp) or []

        # FIXME: move filter to webserver API (next PR)
        projects: Deque[Project] = deque()
        for prj in data:
            if prj.get("name", "") == solver_name:
                try:
                    projects.append(Project.parse_obj(prj))
                except ValidationError as err:
                    logger.warning(
                        "Invalid prj %s [%s]: %s", prj.get("uuid"), solver_name, err
                    )

        return list(projects)


# TODO: init client and then build sessions from client using depenencies
#
# from ..utils.client_base import BaseServiceClientApi
# class WebserverApi(BaseServiceClientApi):
#     """ One instance per app """

#     def create_auth_session(self, session_cookies) -> AuthSession:
#         """ Needed per request, so it can perform """
#         return AuthSession(client=self.client, vtag="v0", session_cookies=session_cookies)
