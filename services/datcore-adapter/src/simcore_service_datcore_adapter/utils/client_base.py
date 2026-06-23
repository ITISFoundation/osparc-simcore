import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State

from .app_data import AppDataMixin

_logger = logging.getLogger(__name__)


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
            resp = await self.client.get(self.health_check_path, timeout=self.health_check_timeout)
            resp.raise_for_status()
            return True
        except (httpx.HTTPStatusError, httpx.RequestError):
            _logger.exception("%s not responsive", self.service_name)
            return False


# HELPERS -------------------------------------------------------------


def configure_client_instance(
    app: FastAPI,
    app_lifespan: LifespanManager[FastAPI],
    api_cls: type[BaseServiceClientApi],
    api_baseurl: str,
    service_name: str,
    api_general_timeout: float = 5.0,
    **extra_fields,
) -> None:
    """Helper to add init/cleanup of ServiceClientApi instances in the app lifespan manager."""

    assert issubclass(api_cls, BaseServiceClientApi)

    async def _client_lifespan(_: FastAPI) -> AsyncIterator[State]:
        # NOTE: http2 is explicitly disabled due to the issue https://github.com/encode/httpx/discussions/2112
        api_cls.create_once(
            app,
            client=httpx.AsyncClient(http2=False, base_url=api_baseurl, timeout=api_general_timeout),
            service_name=service_name,
            **extra_fields,
        )
        try:
            yield {}
        finally:
            api_obj: BaseServiceClientApi | None = api_cls.pop_instance(app)
            if api_obj:
                await api_obj.client.aclose()

    app_lifespan.add(_client_lifespan)
