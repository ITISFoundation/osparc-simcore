import logging
from contextlib import suppress
from dataclasses import dataclass

import httpx
from fastapi import FastAPI

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
        except (httpx.HTTPStatusError, httpx.RequestError) as err:
            _logger.error("%s not responsive: %s", self.service_name, err)
            return False

    ping = is_responsive  # alias


# HELPERS -------------------------------------------------------------


def setup_client_instance(
    app: FastAPI,
    api_cls: type[BaseServiceClientApi],
    api_baseurl,
    service_name: str,
    **extra_fields,
) -> None:
    """Helper to add init/cleanup of ServiceClientApi instances in the app lifespam"""

    assert issubclass(api_cls, BaseServiceClientApi)  # nosec

    # Http client class
    client: httpx.AsyncClient = httpx.AsyncClient(base_url=api_baseurl)
    with suppress(AttributeError):
        # NOTE that this is a general function with no guarantees as when is going to be used.
        # Here, 'AttributeError' might be raied when app.state.settings is still not initialized
        if capture_path := app.state.settings.API_SERVER_DEV_HTTP_CALLS_LOGS_PATH:
            from .client_base_dev import AsyncClientForDevelopmentOnly

            client = AsyncClientForDevelopmentOnly(
                capture_file=capture_path, base_url=api_baseurl
            )

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
