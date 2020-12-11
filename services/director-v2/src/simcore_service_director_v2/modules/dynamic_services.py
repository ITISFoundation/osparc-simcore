""" Module that takes care of communications with dynamic services v0


"""
import logging
from dataclasses import dataclass

import httpx
from fastapi import FastAPI, Response

# Module's business logic ---------------------------------------------
from ..core.settings import DynamicServicesSettings
from ..utils.client_decorators import handle_errors, handle_retry

logger = logging.getLogger(__name__)


# Module's setup logic ---------------------------------------------


def setup(app: FastAPI, settings: DynamicServicesSettings):
    if not settings:
        settings = DynamicServicesSettings()

    def on_startup() -> None:
        ServicesClient.create(
            app,
            client=httpx.AsyncClient(
                timeout=app.state.settings.client_request.total_timeout
            ),
        )

    async def on_shutdown() -> None:
        client = ServicesClient.instance(app).client
        await client.aclose()
        del app.state.dynamic_services_client

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


@dataclass
class ServicesClient:
    client: httpx.AsyncClient

    @classmethod
    def create(cls, app: FastAPI, **kwargs):
        app.state.dynamic_services_client = cls(**kwargs)
        return cls.instance(app)

    @classmethod
    def instance(cls, app: FastAPI):
        return app.state.dynamic_services_client

    @handle_errors("DynamicService", logger)
    @handle_retry(logger)
    async def request(self, method: str, tail_path: str, **kwargs) -> Response:
        return await self.client.request(method, tail_path, **kwargs)
