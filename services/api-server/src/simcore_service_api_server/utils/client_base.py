import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Final

import httpx
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from httpx import AsyncClient, Timeout
from servicelib.fastapi.tracing import get_tracing_config
from servicelib.tracing import setup_httpx_client_tracing
from settings_library.tracing import TracingSettings

from .app_data import AppDataMixin

_logger = logging.getLogger(__name__)

_DEFAULT_BASE_SERVICE_CLIENT_API_TIMEOUT_SECONDS: Final[int] = 60


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

    async def is_responsive(self) -> bool:
        try:
            resp = await self.client.get(self.health_check_path, timeout=1)
            resp.raise_for_status()
            return True
        except (httpx.HTTPStatusError, httpx.RequestError):
            return False

    ping = is_responsive  # alias


# HELPERS -------------------------------------------------------------


def configure_client_instance(
    app: FastAPI,
    app_lifespan: LifespanManager[FastAPI],
    api_cls: type[BaseServiceClientApi],
    api_baseurl: str,
    service_name: str,
    tracing_settings: TracingSettings | None,
    **extra_fields,
) -> None:
    """Helper to add init/cleanup of ServiceClientApi instances in the app lifespam"""

    assert issubclass(api_cls, BaseServiceClientApi)  # nosec

    async def _client_lifespan(lifespan_app: FastAPI) -> AsyncIterator[State]:
        # NOTE: this term is mocked in tests. If you need to modify pay attention to the mock
        client = AsyncClient(
            base_url=api_baseurl,
            timeout=Timeout(_DEFAULT_BASE_SERVICE_CLIENT_API_TIMEOUT_SECONDS),
        )
        _logger.debug("Creating %s for %s", f"{type(client)=}", f"{api_baseurl=}")
        try:
            if tracing_settings:
                setup_httpx_client_tracing(
                    client,
                    tracing_config=get_tracing_config(app),
                )
            api_cls.create_once(
                lifespan_app,
                client=client,
                service_name=service_name,
                **extra_fields,
            )
            yield {}
        finally:
            api_obj: BaseServiceClientApi | None = api_cls.pop_instance(lifespan_app)
            await (api_obj.client if api_obj else client).aclose()

    app_lifespan.add(_client_lifespan)
