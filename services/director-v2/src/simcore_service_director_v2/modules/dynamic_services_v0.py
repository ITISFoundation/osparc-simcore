""" Module that takes care of communications with dynamic services v0


"""
import logging
from dataclasses import dataclass

import httpx
from fastapi import FastAPI, Response

# Module's business logic ---------------------------------------------
from ..core.settings import DynamicServicesV0Settings
from ..utils.client_decorators import handle_errors, handle_retry

logger = logging.getLogger(__name__)


# Module's setup logic ---------------------------------------------


def setup(app: FastAPI, settings: DynamicServicesV0Settings):
    if not settings:
        settings = DynamicServicesV0Settings()

    def on_startup() -> None:
        ServicesV0Client.create(
            app,
            client=httpx.AsyncClient(base_url=settings.base_url(include_tag=True)),
        )

    async def on_shutdown() -> None:
        client = ServicesV0Client.instance(app).client
        await client.aclose()
        del app.state.dynamic_services_v0_client

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


@dataclass
class ServicesV0Client:
    client: httpx.AsyncClient

    @classmethod
    def create(cls, app: FastAPI, **kwargs):
        app.state.dynamic_services_v0_client = cls(**kwargs)
        return cls.instance(app)

    @classmethod
    def instance(cls, app: FastAPI):
        return app.state.dynamic_services_v0_client

    @handle_errors("DynamicService", logger)
    @handle_retry(logger)
    async def request(self, method: str, tail_path: str, **kwargs) -> Response:
        return await self.client.request(method, tail_path, **kwargs)
