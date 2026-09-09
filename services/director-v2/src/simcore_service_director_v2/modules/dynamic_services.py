"""Module that takes care of communications with dynamic services v0"""

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.fastapi.tracing import get_tracing_config
from servicelib.tracing import setup_httpx_client_tracing

from ..utils.client_decorators import handle_errors, handle_retry

logger = logging.getLogger(__name__)


def configure_dynamic_services(app_lifespan: LifespanManager) -> None:
    async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
        client = httpx.AsyncClient(timeout=app.state.settings.CLIENT_REQUEST.HTTP_CLIENT_REQUEST_TOTAL_TIMEOUT)
        if get_tracing_config(app).tracing_enabled:
            setup_httpx_client_tracing(
                client=client,
                tracing_config=get_tracing_config(app=app),
            )
        ServicesClient.create(
            app,
            client=client,
        )
        try:
            yield
        finally:
            await client.aclose()
            del app.state.dynamic_services_client

    app_lifespan.add(_lifespan)


@dataclass
class ServicesClient:
    client: httpx.AsyncClient

    @classmethod
    def create(cls, app: FastAPI, **kwargs) -> "ServicesClient":
        app.state.dynamic_services_client = cls(**kwargs)
        return cls.instance(app)

    @classmethod
    def instance(cls, app: FastAPI) -> "ServicesClient":
        client: ServicesClient = app.state.dynamic_services_client
        return client

    @handle_errors("DynamicService", logger)
    @handle_retry(logger)
    async def request(self, method: str, tail_path: str, **kwargs) -> httpx.Response:
        return await self.client.request(method, tail_path, **kwargs)
