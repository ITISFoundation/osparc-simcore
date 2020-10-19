import logging
from dataclasses import dataclass
from typing import Dict, Iterator

import httpx
from fastapi import FastAPI

from ..core.settings import DirectorV0Settings
from .client_utils import errors_middleware, retry_middleware

logger = logging.getLogger(__name__)


def on_start(app: FastAPI) -> None:
    settings: DirectorV0Settings = app.state.settings.director_v0
    app.state.director_v0_client = DirectorV0Client(
        client=httpx.AsyncClient(base_url=settings.api_base_url)
    )


async def on_stop(app: FastAPI) -> None:
    await app.state.director_v0_client.client.aclose()
    del app.state.director_v0_client


# TODO: add this functionlity
async def on_cleanup_context(app: FastAPI) -> Iterator[None]:
    settings: DirectorV0Settings = app.state.settings.director_v0
    async with httpx.AsyncClient(base_url=settings.api_base_url) as client:
        app.state.director_v0_client = DirectorV0Client(client)

        yield

    del app.state.director_v0_client


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

    @errors_middleware("Director", logger)
    @retry_middleware(logger)
    async def request(self, method: str, tail_path: str, **kwargs) -> Dict:
        resp = await self.client.request(method, tail_path, **kwargs)
        return resp.json()
