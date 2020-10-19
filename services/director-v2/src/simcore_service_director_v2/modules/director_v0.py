""" Module that takes care of communications with director v0 service


"""
import logging
from dataclasses import dataclass

import httpx
from fastapi import FastAPI

from ..core.settings import DirectorV0Settings
from ..utils.client_policies import handle_response, handle_retry

logger = logging.getLogger(__name__)


# Module's setup logic ---------------------------------------------

def setup(app: FastAPI, settings: DirectorV0Settings):
    if not settings:
        settings = DirectorV0Settings()

    def on_startup() -> None:
        DirectorV0Client.create(
            app, client=httpx.AsyncClient(base_url=settings.base_url(include_tag=True))
        )

    async def on_shutdown() -> None:
        client = DirectorV0Client.instance(app).client
        await client.aclose()
        del app.state.director_v0_client

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


# Module's business logic ---------------------------------------------


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

    @handle_response("Director", logger)
    @handle_retry(logger)
    async def request(self, method: str, tail_path: str, **kwargs):
        return await self.client.request(method, tail_path, **kwargs)
