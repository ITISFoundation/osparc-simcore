import logging
import traceback
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI

from ...core.settings import DynamicSidecarSettings
from ...models.schemas.dynamic_services import MonitorData

logger = logging.getLogger(__name__)


def get_url(dynamic_sidecar_endpoint: str, postfix: str) -> str:
    """formats and returns an url for the request"""
    url = f"{dynamic_sidecar_endpoint}{postfix}"
    return url


class DynamicSidecarClient:
    """Will handle connections to the service sidecar"""

    def __init__(self, app: FastAPI):
        self._app = app
        self._heatlth_request_timeout = httpx.Timeout(1.0, connect=1.0)

        dynamic_sidecar_settings: DynamicSidecarSettings = (
            app.state.settings.dynamic_services.dynamic_sidecar
        )

        self.httpx_client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                dynamic_sidecar_settings.DYNAMIC_SIDECAR_API_REQUEST_TIMEOUT,
                connect=1.0,
            )
        )

    async def close(self):
        await self.httpx_client.aclose()

    async def is_healthy(self, dynamic_sidecar_endpoint: str) -> bool:
        """retruns True if service is UP and running else False"""
        url = get_url(dynamic_sidecar_endpoint, "/health")
        try:
            # this request uses a very short timeout
            response = await self.httpx_client.get(
                url=url, timeout=self._heatlth_request_timeout
            )
            if response.status_code != 200:
                return False

            return response.json()["is_healthy"]
        except httpx.HTTPError:
            return False


async def setup_api_client(app: FastAPI) -> None:
    logger.debug("dynamic-sidecar api client setup")
    app.state.dynamic_sidecar_api_client = DynamicSidecarClient(app)


async def shutdown_api_client(app: FastAPI) -> None:
    logger.debug("dynamic-sidecar api client shutdown")
    dynamic_sidecar_api_client = app.state.dynamic_sidecar_api_client
    await dynamic_sidecar_api_client.close()


def get_dynamic_sidecar_client(app: FastAPI) -> DynamicSidecarClient:
    return app.state.dynamic_sidecar_api_client


async def update_dynamic_sidecar_health(
    app: FastAPI, monitor_data: MonitorData
) -> None:

    api_client = get_dynamic_sidecar_client(app)
    service_endpoint = monitor_data.dynamic_sidecar.endpoint

    # update service health
    is_healthy = await api_client.is_healthy(service_endpoint)
    monitor_data.dynamic_sidecar.is_available = is_healthy
