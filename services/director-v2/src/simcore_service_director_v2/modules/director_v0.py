""" Module that takes care of communications with director v0 service


"""
import logging
import urllib
from dataclasses import dataclass

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from models_library.projects_nodes import NodeID
from models_library.services import ServiceDockerData, ServiceKeyVersion

# Module's business logic ---------------------------------------------
from starlette import status
from starlette.datastructures import URL

from ..core.settings import DirectorV0Settings
from ..models.schemas.services import RunningServiceDetails, ServiceExtras
from ..utils.client_decorators import handle_errors, handle_retry
from ..utils.clients import unenvelope_or_raise_error
from ..utils.logging_utils import log_decorator

logger = logging.getLogger(__name__)

# Module's setup logic ---------------------------------------------


def setup(app: FastAPI, settings: DirectorV0Settings):
    if not settings:
        settings = DirectorV0Settings()

    def on_startup() -> None:
        DirectorV0Client.create(
            app,
            client=httpx.AsyncClient(
                base_url=settings.base_url(include_tag=True), timeout=1.0
            ),
        )

    async def on_shutdown() -> None:
        client = DirectorV0Client.instance(app).client
        await client.aclose()
        del app.state.director_v0_client

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


@dataclass
class DirectorV0Client:
    client: httpx.AsyncClient

    @classmethod
    def create(cls, app: FastAPI, **kwargs):
        app.state.director_v0_client = cls(**kwargs)
        return cls.instance(app)

    @classmethod
    def instance(cls, app: FastAPI):
        return app.state.director_v0_client

    @handle_errors("Director", logger)
    @handle_retry(logger)
    async def request(self, method: str, tail_path: str, **kwargs) -> Response:
        return await self.client.request(method, tail_path, **kwargs)

    async def forward(self, request: Request, response: Response) -> Response:
        url_tail = URL(
            path=request.url.path.replace("/v0", ""),
            fragment=request.url.fragment,
        )
        body: bytes = await request.body()

        resp = await self.client.request(
            request.method,
            str(url_tail),
            params=dict(request.query_params),
            data=body,
            headers=dict(request.headers),
        )

        # Prepared response
        response.body = resp.content
        response.status_code = resp.status_code
        response.headers.update(resp.headers)

        # NOTE: the response is NOT validated!
        return response

    @log_decorator(logger=logger)
    async def get_service_details(
        self, service: ServiceKeyVersion
    ) -> ServiceDockerData:
        resp = await self.request(
            "GET", f"services/{urllib.parse.quote_plus(service.key)}/{service.version}"
        )
        if resp.status_code == status.HTTP_200_OK:
            return ServiceDockerData.parse_obj(unenvelope_or_raise_error(resp)[0])
        raise HTTPException(status_code=resp.status_code, detail=resp.content)

    @log_decorator(logger=logger)
    async def get_service_extras(self, service: ServiceKeyVersion) -> ServiceExtras:
        resp = await self.request(
            "GET",
            f"service_extras/{urllib.parse.quote_plus(service.key)}/{service.version}",
        )
        if resp.status_code == status.HTTP_200_OK:
            return ServiceExtras.parse_obj(unenvelope_or_raise_error(resp))
        raise HTTPException(status_code=resp.status_code, detail=resp.content)

    @log_decorator(logger=logger)
    async def get_running_service_details(
        self, service_uuid: NodeID
    ) -> RunningServiceDetails:
        resp = await self.request("GET", f"running_interactive_services/{service_uuid}")
        if resp.status_code == status.HTTP_200_OK:
            return RunningServiceDetails.parse_obj(unenvelope_or_raise_error(resp))
        raise HTTPException(status_code=resp.status_code, detail=resp.content)
