"""

services/director/src/simcore_service_director/registry_proxy.py
services/director/src/simcore_service_director/registry_cache_task.py

"""
import logging
from contextlib import suppress
from typing import Dict, List

from fastapi import FastAPI
from httpx import AsyncClient

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
#
#
# TODO: create a fetcher around the client whose responsitiblity is
#    - retrial
#    - circuit breaker
#    - diagnostic tracker
#    - cache?
#


class RegistryApiClient:
    """

    Basic Authentication or Bearer
    """

    def __init__(self, settings: RegistrySettings):
        self.settings = settings.copy()

        # TODO: add auth https://www.python-httpx.org/advanced/#customizing-authentication
        # TODO: see https://colin-b.github.io/httpx_auth/

        self.client = AsyncClient(
            base_url=self.settings.api_url(with_credentials=False)
        )

    def get_basic_auth(self):
        auth = (self.settings.user, self.settings.pw.get_secret_value())
        return auth

    async def list_repositories(self, number_of_retrieved_repos=50) -> List[str]:
        ## r"^<https://foo\.com\/v2\/(.*)>\;"
        r = await self.client.get("/_catalog", params={"n": number_of_retrieved_repos})
        repos = r.json().get("repositories")

        while "Link" in r.headers:
            # regex??  ^<(*.)>;
            next_page = (
                r.headers["Link"]
                .split(";")[0]
                .strip("<>")
                .replace(self.client.base_url, "")
            )
            r = await self.client.get(next_page)
            repos.extend(r.json().get("repositories"))

        # TODO: should we do the validation and
        # returning domain models here or outside??
        return repos

    async def list_image_tags(self, image_tag: str) -> List[str]:
        pass

    async def get_image_labels(self, image: str, tag: str) -> Dict:
        pass

    async def get_image_details(self, image_key: str, image_tag: str) -> Dict:
        pass

    async def get_repo_details(self, image_key: str) -> List[Dict]:
        pass

    async def list_services(
        self,  # service_type: ServiceType
    ) -> List[Dict]:
        pass

    async def list_interactive_service_dependencies(
        self, service_key: str, service_tag: str
    ) -> List[Dict]:
        pass

    async def get_service_extras(
        self, image_key: str, image_tag: str
    ) -> Dict[str, str]:
        pass
