""" Module responsible of communicating with docker registry API

"""
# TODO: code below simply copied from old director and partially adapted
# services/director/src/simcore_service_director/registry_proxy.py
# services/director/src/simcore_service_director/registry_cache_task.py
import logging
from contextlib import suppress
from typing import Dict, List

from fastapi import FastAPI
from httpx import AsyncClient

from ..core.settings import RegistrySettings

logger = logging.getLogger(__name__)

# Module's setup logic ---------------------------------------------


def setup(app: FastAPI, settings: RegistrySettings):
    if not settings:
        settings = RegistrySettings()

    def on_startup() -> None:
        app.state.docker_registry_api = RegistryApiClient(settings)

    async def on_shutdown() -> None:
        with suppress(AttributeError):
            client: AsyncClient = app.state.docker_registry_api.client
            await client.aclose()
            del app.state.docker_registry_api

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


# Module's business logic ---------------------------------------------
#
# TODO: this is totally unfinished!!
# TODO: use utils.client_decorators to implement
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

        self.client = AsyncClient(base_url=self.settings.api_url, timeout=20)

    def get_basic_auth(self):
        auth = (self.settings.user, self.settings.pw.get_secret_value())
        return auth

    async def list_repositories(self, number_of_retrieved_repos=50) -> List[str]:
        # NOTE: r"^<https://foo\.com\/v2\/(.*)>\;"
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

    async def list_image_tags(self, image_key: str) -> List[str]:
        raise NotImplementedError()

    async def get_image_labels(self, image_key: str, tag: str) -> Dict:
        raise NotImplementedError()

    async def get_image_details(self, image_key: str, image_tag: str) -> Dict:
        raise NotImplementedError()

    async def get_repo_details(self, image_key: str) -> List[Dict]:
        raise NotImplementedError()

    async def list_services(
        self,  # service_type: ServiceType
    ) -> List[Dict]:
        raise NotImplementedError()

    async def list_interactive_service_dependencies(
        self, service_key: str, service_tag: str
    ) -> List[Dict]:
        raise NotImplementedError()

    async def get_service_extras(
        self, image_key: str, image_tag: str
    ) -> Dict[str, str]:
        raise NotImplementedError()
