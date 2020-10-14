"""

services/director/src/simcore_service_director/registry_proxy.py
services/director/src/simcore_service_director/registry_cache_task.py

"""
from contextlib import suppress
from typing import List

from fastapi import FastAPI
from httpx import AsyncClient

from ..core.settings import RegistrySettings


def setup_docker_registry(app: FastAPI) -> None:
    settings: RegistrySettings = app.state.settings.registry

    # adds client to access Registry API
    app.state.docker_registry_api = RegistryApiClient(settings.api_url)


async def shutdown_docker_registry(app: FastAPI) -> None:
    with suppress(AttributeError):
        client: AsyncClient = app.state.docker_registry_api.client
        await client.aclose()
        del app.state.docker_registry_api


# ----------------------------


class RegistryApiClient:
    def __init__(self, api_url):
        self.client = AsyncClient(base_url=api_url)

    async def list_repositories() -> List[str]:
        pass

    async def list_image_tags() -> List[str]:
        pass
