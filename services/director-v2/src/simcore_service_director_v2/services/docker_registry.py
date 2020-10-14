# services/director/src/simcore_service_director/registry_proxy.py
# services/director/src/simcore_service_director/registry_cache_task.py
from typing import List

import httpx
from fastapi import FastAPI

from ..core.settings import RegistrySettings


def setup_docker_registry(app: FastAPI) -> None:
    settings: RegistrySettings = app.state.settings.registry

    # TODO: adds client to access Registry API
    app.state.docker_registry_api = RegistryApiClient


def shutdown_docker_registry(app: FastAPI) -> None:
    pass


class RegistryApiClient:
    def __init__(self, settings: RegistrySettings):
        self.client = httpx.AsyncClient(base_url=str(settings.url))

    async def list_repositories() -> List[str]:
        pass

    async def list_image_tags() -> List[str]:
        pass
