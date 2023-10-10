import json
import logging
import urllib.parse
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx
from cryptography import fernet
from fastapi import FastAPI, HTTPException
from httpx import Response
from models_library.api_schemas_webserver.projects import ProjectCreateNew, ProjectGet
from models_library.api_schemas_webserver.projects_metadata import (
    ProjectMetadataGet,
    ProjectMetadataUpdate,
)
from models_library.api_schemas_webserver.wallets import WalletGet
from models_library.generics import Envelope
from models_library.projects import ProjectID
from models_library.rest_pagination import Page
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import ValidationError
from pydantic.errors import PydanticErrorMixin
from servicelib.aiohttp.long_running_tasks.server import TaskStatus
from servicelib.error_codes import create_error_code
from starlette import status
from tenacity import TryAgain
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

from ..core.settings import WebServerSettings
from ..models.pagination import MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE
from ..models.schemas.jobs import MetaValueType
from ..models.types import AnyJson
from ..utils.client_base import BaseServiceClientApi, setup_client_instance

_logger = logging.getLogger(__name__)


class WebServerValueError(PydanticErrorMixin, ValueError):
    ...


class ProjectNotFoundError(WebServerValueError):
    code = "webserver.project_not_found"
    msg_template = "Project '{project_id}' not found"


@contextmanager
def _handle_webserver_api_errors():
    # Transforms httpx.errors and ValidationError -> fastapi.HTTPException
    try:
        yield

    except ValidationError as exc:
        # Invalid formatted response body
        error_code = create_error_code(exc)
        _logger.exception(
            "Invalid data exchanged with webserver service [%s]",
            error_code,
            extra={"error_code": error_code},
        )
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail=error_code
        ) from exc

    except httpx.RequestError as exc:
        # e.g. TransportError, DecodingError, TooManyRedirects
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE) from exc

    except httpx.HTTPStatusError as exc:
        resp = exc.response
        if resp.is_server_error:
            _logger.exception(
                "webserver reponded with an error: %s [%s]",
                f"{resp.status_code=}",
                f"{resp.reason_phrase=}",
            )
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE) from exc

        if resp.is_client_error:
            # NOTE: Raise ProjectErrors / WebserverError that should be transformed into HTTP errors on the handler level
            error = exc.response.json().get("error", {})
            msg = error.get("errors") or resp.reason_phrase or f"{exc}"
            raise HTTPException(resp.status_code, detail=msg) from exc


class WebserverApi(BaseServiceClientApi):
    """Access to web-server API

    - BaseServiceClientApi:
        - wraps a httpx client
        - lifetime attached to app
        - responsive tests (i.e. ping) to API in-place

    """


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

    _api: WebserverApi
    vtag: str
    session_cookies: dict | None = None

    @classmethod
    def create(cls, app: FastAPI, session_cookies: dict) -> "AuthSession":
        api = WebserverApi.get_instance(app)
        assert api  # nosec
        assert isinstance(api, WebserverApi)  # nosec
        return cls(
            _api=api,
            vtag=app.state.settings.API_SERVER_WEBSERVER.WEBSERVER_VTAG,
            session_cookies=session_cookies,
        )

    @classmethod
    def _get_data_or_raise(
        cls,
        resp: Response,
        client_status_code_to_exception_map: dict[int, WebServerValueError]
        | None = None,
    ) -> AnyJson | None:
        """
        Raises:
            WebServerValueError: any client error converted to module error
            HTTPException: the rest are pre-process and raised as http errors

        """
        # enveloped answer
        data: AnyJson | None = None
        error: AnyJson | None = None

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
                "webserver reponded with an error: %s [%s]: %s",
                f"{resp.status_code=}",
                f"{resp.reason_phrase=}",
                error,
            )
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE)

        if resp.is_client_error:
            # Maps client status code to webserver local module error
            if client_status_code_to_exception_map and (
                exc := client_status_code_to_exception_map.get(resp.status_code)
            ):
                raise exc

            # Otherwise, go thru with some pre-processing to make
            # message cleaner
            if isinstance(error, dict):
                error = error.get("message")

            msg = error or resp.reason_phrase
            raise HTTPException(resp.status_code, detail=msg)

        return data

    # OPERATIONS

    @property
    def client(self):
        return self._api.client

    async def get(self, path: str) -> AnyJson | None:
        url = path.lstrip("/")
        try:
            resp = await self.client.get(url, cookies=self.session_cookies)
        except Exception as err:
            _logger.exception("Failed to get %s", url)
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE) from err

        return self._get_data_or_raise(resp)

    async def put(self, path: str, body: dict) -> AnyJson | None:
        url = path.lstrip("/")
        try:
            resp = await self.client.put(url, json=body, cookies=self.session_cookies)
        except Exception as err:
            _logger.exception("Failed to put %s", url)
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE) from err

        return self._get_data_or_raise(resp)

    async def _page_projects(
        self, *, limit: int, offset: int, show_hidden: bool, search: str | None = None
    ):
        assert 1 <= limit <= MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE  # nosec
        assert offset >= 0  # nosec

        optional: dict[str, Any] = {}
        if search is not None:
            optional["search"] = search

        with _handle_webserver_api_errors():
            resp = await self.client.get(
                "/projects",
                params={
                    "type": "user",
                    "show_hidden": show_hidden,
                    "limit": limit,
                    "offset": offset,
                    **optional,
                },
                cookies=self.session_cookies,
            )
            resp.raise_for_status()

            return Page[ProjectGet].parse_raw(resp.text)

    async def _wait_for_long_running_task_results(self, data):
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
                status_data = await self.get(status_url)
                task_status = TaskStatus.parse_obj(status_data)
                if not task_status.done:
                    msg = "Timed out creating project. TIP: Try again, or contact oSparc support if this is happening repeatedly"
                    raise TryAgain(msg)

        return await self.get(f"{result_url}")

    # PROJECTS -------------------------------------------------

    async def create_project(self, project: ProjectCreateNew) -> ProjectGet:
        # POST /projects --> 202 Accepted
        response = await self.client.post(
            "/projects",
            params={"hidden": True},
            json=jsonable_encoder(project, by_alias=True, exclude={"state"}),
            cookies=self.session_cookies,
        )
        data = self._get_data_or_raise(response)
        assert data is not None  # nosec

        result = await self._wait_for_long_running_task_results(data)
        return ProjectGet.parse_obj(result)

    async def clone_project(self, project_id: UUID) -> ProjectGet:
        response = await self.client.post(
            f"/projects/{project_id}:clone",
            cookies=self.session_cookies,
        )
        data = self._get_data_or_raise(
            response,
            {status.HTTP_404_NOT_FOUND: ProjectNotFoundError(project_id=project_id)},
        )
        assert data is not None  # nosec

        result = await self._wait_for_long_running_task_results(data)
        return ProjectGet.parse_obj(result)

    async def get_project(self, project_id: UUID) -> ProjectGet:
        response = await self.client.get(
            f"/projects/{project_id}",
            cookies=self.session_cookies,
        )

        data = self._get_data_or_raise(
            response,
            {status.HTTP_404_NOT_FOUND: ProjectNotFoundError(project_id=project_id)},
        )
        return ProjectGet.parse_obj(data)

    async def get_projects_w_solver_page(
        self, solver_name: str, limit: int, offset: int
    ) -> Page[ProjectGet]:
        return await self._page_projects(
            limit=limit,
            offset=offset,
            show_hidden=True,
            # WARNING: better way to match jobs with projects (Next PR if this works fine!)
            # WARNING: search text has a limit that I needed to increase for the example!
            search=urllib.parse.quote(solver_name, safe=""),
        )

    async def get_projects_page(self, limit: int, offset: int):
        return await self._page_projects(
            limit=limit,
            offset=offset,
            show_hidden=False,
        )

    async def delete_project(self, project_id: ProjectID) -> None:
        response = await self.client.delete(
            f"/projects/{project_id}", cookies=self.session_cookies
        )
        data = self._get_data_or_raise(
            response,
            {status.HTTP_404_NOT_FOUND: ProjectNotFoundError(project_id=project_id)},
        )
        assert data is None  # nosec

    async def get_project_metadata_ports(
        self, project_id: ProjectID
    ) -> list[dict[str, Any]]:
        """
        maps GET "/projects/{study_id}/metadata/ports", unenvelopes
        and returns data
        """
        response = await self.client.get(
            f"/projects/{project_id}/metadata/ports",
            cookies=self.session_cookies,
        )

        data = self._get_data_or_raise(
            response,
            {status.HTTP_404_NOT_FOUND: ProjectNotFoundError(project_id=project_id)},
        )
        assert data is not None
        assert isinstance(data, list)
        return data

    async def get_project_metadata(self, project_id: ProjectID) -> ProjectMetadataGet:
        with _handle_webserver_api_errors():
            response = await self.client.get(
                f"/projects/{project_id}/metadata",
                cookies=self.session_cookies,
            )
            response.raise_for_status()
            data = Envelope[ProjectMetadataGet].parse_raw(response.text).data
            assert data  # nosec
            return data

    async def update_project_metadata(
        self, project_id: ProjectID, metadata: dict[str, MetaValueType]
    ) -> ProjectMetadataGet:
        with _handle_webserver_api_errors():
            response = await self.client.patch(
                f"/projects/{project_id}/metadata",
                cookies=self.session_cookies,
                json=jsonable_encoder(ProjectMetadataUpdate(custom=metadata)),
            )
            response.raise_for_status()
            data = Envelope[ProjectMetadataGet].parse_raw(response.text).data
            assert data  # nosec
            return data

    async def get_project_wallet(self, project_id: ProjectID) -> WalletGet:
        with _handle_webserver_api_errors():
            response = await self.client.get(
                f"/projects/{project_id}/wallet",
                cookies=self.session_cookies,
            )
            response.raise_for_status()
            data = Envelope[WalletGet].parse_raw(response.text).data
            return data

    # WALLETS -------------------------------------------------

    async def get_wallet(self, wallet_id: int) -> WalletGet:
        with _handle_webserver_api_errors():
            response = await self.client.get(
                f"/wallets/{wallet_id}",
                cookies=self.session_cookies,
            )
            response.raise_for_status()
            data = Envelope[WalletGet].parse_raw(response.text).data
            assert data  # nosec
            return data


# MODULES APP SETUP -------------------------------------------------------------


def setup(app: FastAPI, settings: WebServerSettings | None = None) -> None:
    if not settings:
        settings = WebServerSettings.create_from_envs()

    assert settings is not None  # nosec

    setup_client_instance(
        app, WebserverApi, api_baseurl=settings.api_base_url, service_name="webserver"
    )

    def _on_startup() -> None:
        # normalize & encrypt
        secret_key = settings.WEBSERVER_SESSION_SECRET_KEY.get_secret_value()
        app.state.webserver_fernet = fernet.Fernet(secret_key)

    async def _on_shutdown() -> None:
        _logger.debug("Webserver closed successfully")

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)
