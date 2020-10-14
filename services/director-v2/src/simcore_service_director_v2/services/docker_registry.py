"""

services/director/src/simcore_service_director/registry_proxy.py
services/director/src/simcore_service_director/registry_cache_task.py

"""
from contextlib import suppress
from typing import List

from fastapi import FastAPI
from httpx import AsyncClient
import logging

from ..core.settings import RegistrySettings


logger = logging.getLogger(__name__)

def setup_docker_registry(app: FastAPI) -> None:
    settings: RegistrySettings = app.state.settings.registry
    app.state.docker_registry_api = RegistryApiClient(settings)


async def shutdown_docker_registry(app: FastAPI) -> None:
    with suppress(AttributeError):
        client: AsyncClient = app.state.docker_registry_api.client
        await client.aclose()
        del app.state.docker_registry_api


# ----------------------------


class RegistryApiClient:
    """

        Basic Authentication or Bearer
    """

    def __init__(self, settings: RegistrySettings):
        self.settings = settings.copy()

        # TODO: add auth https://www.python-httpx.org/advanced/#customizing-authentication
        # TODO: see https://colin-b.github.io/httpx_auth/

        self.client = AsyncClient(base_url=self.settings.api_url(with_credentials=False))

    def get_basic_auth(self):
        auth=(self.settings.user, self.settings.pw.get_secret_value())
        return auth


    async def list_repositories(self, number_of_retrieved_repos=50) -> List[str]:

        while True:
            r = await client.get("_catalog", params={"n":number_of_retrieved_repos})
            body = r.json()
            if body.get("repositories"):
                repos.extend()



    async def list_image_tags() -> List[str]:
        pass
