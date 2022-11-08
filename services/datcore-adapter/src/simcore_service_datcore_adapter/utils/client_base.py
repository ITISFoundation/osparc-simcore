import logging
from dataclasses import dataclass
from typing import Optional

import httpx
from fastapi import FastAPI

from .app_data import AppDataMixin

log = logging.getLogger(__name__)


@dataclass
class BaseServiceClientApi(AppDataMixin):
    """
    - wrapper around thin-client to simplify service's API calls
    - sets endspoint upon construction
    - MIME type: application/json
    - processes responses, returning data or raising formatted HTTP exception
    - helpers to create a unique client instance per application and service
    """

    client: httpx.AsyncClient
    service_name: str
    health_check_path: str = "/"
    health_check_timeout: float = 1.0

    async def is_responsive(self) -> bool:
        try:
            resp = await self.client.get(
                self.health_check_path, timeout=self.health_check_timeout
            )
            resp.raise_for_status()
            return True
        except (httpx.HTTPStatusError, httpx.RequestError) as err:
            log.error("%s not responsive: %s", self.service_name, err)
            return False


# HELPERS -------------------------------------------------------------


def setup_client_instance(
    app: FastAPI,
    api_cls: type[BaseServiceClientApi],
    api_baseurl: str,
    service_name: str,
    api_general_timeout: float = 5.0,
    **extra_fields
) -> None:
    """Helper to add init/cleanup of ServiceClientApi instances in the app lifespam"""

    assert issubclass(api_cls, BaseServiceClientApi)

    def _create_instance() -> None:
        # NOTE: http2 is explicitely disabled due to the issue https://github.com/encode/httpx/discussions/2112
        api_cls.create_once(
            app,
            client=httpx.AsyncClient(
                http2=False, base_url=api_baseurl, timeout=api_general_timeout
            ),
            service_name=service_name,
            **extra_fields
        )

    async def _cleanup_instance() -> None:
        api_obj: Optional[BaseServiceClientApi] = api_cls.pop_instance(app)
        if api_obj:
            await api_obj.client.aclose()

    app.add_event_handler("startup", _create_instance)
    app.add_event_handler("shutdown", _cleanup_instance)
