import logging
from dataclasses import dataclass

import httpx
from fastapi import FastAPI
from httpx import AsyncClient
from servicelib.fastapi.tracing import setup_httpx_client_tracing
from settings_library.tracing import TracingSettings

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

    async def is_responsive(self) -> bool:
        try:
            resp = await self.client.get(self.health_check_path, timeout=1)
            resp.raise_for_status()
            return True
        except (httpx.HTTPStatusError, httpx.RequestError):
            return False

    ping = is_responsive  # alias


# HELPERS -------------------------------------------------------------


def setup_client_instance(
    app: FastAPI,
    api_cls: type[BaseServiceClientApi],
    api_baseurl,
    service_name: str,
    tracing_settings: TracingSettings | None,
    **extra_fields,
) -> None:
    """Helper to add init/cleanup of ServiceClientApi instances in the app lifespam"""

    assert issubclass(api_cls, BaseServiceClientApi)  # nosec
    # NOTE: this term is mocked in tests. If you need to modify pay attention to the mock
    client = AsyncClient(base_url=api_baseurl)
    if tracing_settings:
        setup_httpx_client_tracing(client)

    # events
    def _create_instance() -> None:
        _logger.debug("Creating %s for %s", f"{type(client)=}", f"{api_baseurl=}")
        api_cls.create_once(
            app,
            client=client,
            service_name=service_name,
            **extra_fields,
        )

    async def _cleanup_instance() -> None:
        api_obj: BaseServiceClientApi | None = api_cls.pop_instance(app)
        if api_obj:
            await api_obj.client.aclose()

    app.add_event_handler("startup", _create_instance)
    app.add_event_handler("shutdown", _cleanup_instance)
