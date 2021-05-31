import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List

from cache import AsyncLRU, AsyncTTL
from docker_registry_client import DockerRegistryClient
from fastapi import FastAPI

from ..core.settings import RegistrySettings

MAX_CACHE_ITEMS = 256
# after this interval new services will be seen
# in the cache, currently set at 5 minutes
REPOSITIRES_CACHE_TTL_SECONDS = 5 * 60


def setup_registry(app: FastAPI) -> None:
    settings: RegistrySettings = app.state.settings.registry

    app.state.registry_client = RegistryClient(settings)


class RegistryClient:
    def __init__(self, settings: RegistrySettings):
        self.executor = ThreadPoolExecutor(max_workers=settings.threadpool_max_workers)
        self.client = DockerRegistryClient(settings.address)
        self.loop = asyncio.get_event_loop()

    def _get_labels(self, service_key: str, service_version: str) -> Dict[str, str]:
        manifest, _ = self.client.repository(service_key).manifest(service_version)

        v1_compatibility_key = json.loads(manifest["history"][0]["v1Compatibility"])
        container_config = v1_compatibility_key.get(
            "container_config", v1_compatibility_key["config"]
        )
        return container_config["Labels"]

    def _get_repositories(self) -> List[str]:
        # pylint: disable=unnecessary-comprehension
        return [repository for repository in self.client.repositories()]

    def _get_tags(self, service_key: str) -> List[str]:
        return self.client.repository(service_key).tags()

    @AsyncLRU(maxsize=MAX_CACHE_ITEMS)
    async def get_labels(
        self,
        service_key: str,
        service_version: str,
    ) -> Dict[str, str]:
        return await self.loop.run_in_executor(
            self.executor, self._get_labels, service_key, service_version
        )

    @AsyncTTL(time_to_live=REPOSITIRES_CACHE_TTL_SECONDS, maxsize=1)
    async def get_repositories(self) -> List[str]:
        return await self.loop.run_in_executor(self.executor, self._get_repositories)

    @AsyncLRU(maxsize=MAX_CACHE_ITEMS)
    async def get_tags(self, service_key: str) -> List[str]:
        return await self.loop.run_in_executor(
            self.executor, self._get_tags, service_key
        )
