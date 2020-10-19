import logging
from dataclasses import dataclass
from typing import Dict, Iterator

import httpx
from fastapi import FastAPI

from ..core.settings import DirectorV0Settings
from .client_utils import error_handler, retry_handler

logger = logging.getLogger(__name__)


def on_start(app: FastAPI) -> None:
    settings: DirectorV0Settings = app.state.settings.director_v0
    app.states.director_v0_client = DirectorV0Client(
        client=httpx.AsyncClient(base_url=settings.api_base_url)
    )


async def on_stop(app: FastAPI) -> None:
    await app.state.settings.director_v0.client.aclose()
    del app.state.settings.director_v0_client


# TODO: add this functionlity
async def on_cleanup_context(app: FastAPI) -> Iterator[None]:
    settings: DirectorV0Settings = app.state.settings.director_v0
    async with httpx.AsyncClient(base_url=settings.api_base_url) as client:
        app.states.director_v0_client = DirectorV0Client(client)

        yield

    del app.state.settings.director_v0_client


@dataclass
class DirectorV0Client:
    client: httpx.AsyncClient

    @error_handler
    @retry_handler
    async def request(self, method: str, tail_path: str, **kwargs) -> Dict:
        resp = await self.client.request(method, tail_path, **kwargs)
        return resp.json()
