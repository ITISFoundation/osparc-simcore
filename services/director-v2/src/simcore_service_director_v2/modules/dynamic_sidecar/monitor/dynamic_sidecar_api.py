import logging
import traceback
from typing import Any, Dict, Optional

import httpx
from aiohttp.web import Application

from ..config import get_settings
from .models import MonitorData

logger = logging.getLogger(__name__)


KEY_DYNAMIC_SIDECAR_API_CLIENT = f"{__name__}.DynamicSidecarClient"


def get_url(dynamic_sidecar_endpoint: str, postfix: str) -> str:
    """formats and returns an url for the request"""
    url = f"{dynamic_sidecar_endpoint}{postfix}"
    return url


def log_httpx_http_error(url: str, method: str, formatted_traceback: str) -> None:
    # mainly used to debug issues with the API
    logging.debug(
        (
            "%s -> %s generated:\n %s\nThe above logs can safely "
            "be ignored, except when debugging an issue "
            "regarding the dynamic-sidecar"
        ),
        method,
        url,
        formatted_traceback,
    )


class DynamicSidecarClient:
    """Will handle connections to the service sidecar"""

    def __init__(self, app: Application):
        self._app = app
        self._heatlth_request_timeout = httpx.Timeout(1.0, connect=1.0)

        dynamic_sidecar_settings = get_settings(app)

        self.httpx_client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                dynamic_sidecar_settings.dynamic_sidecar_api_request_timeout,
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

    async def containers_inspect(
        self, dynamic_sidecar_endpoint: str
    ) -> Optional[Dict[str, Any]]:
        """returns: None in case of error, otherwise a dict will be returned"""
        url = get_url(dynamic_sidecar_endpoint, "/v1/containers")
        try:
            response = await self.httpx_client.get(url=url)
            if response.status_code != 200:
                logging.warning(
                    "error during request status=%s, body=%s",
                    response.status_code,
                    response.text,
                )
                return None

            return response.json()
        except httpx.HTTPError:
            log_httpx_http_error(url, "GET", traceback.format_exc())
            return None

    async def containers_docker_status(
        self, dynamic_sidecar_endpoint: str
    ) -> Optional[Dict[str, Dict[str, str]]]:
        """returns: None in case of error, otherwise a dict will be returned"""
        url = get_url(dynamic_sidecar_endpoint, "/v1/containers")
        try:
            response = await self.httpx_client.get(
                url=url, params=dict(only_status=True)
            )
            if response.status_code != 200:
                logging.warning(
                    "error during request status=%s, body=%s",
                    response.status_code,
                    response.text,
                )
                return None

            return response.json()
        except httpx.HTTPError:
            log_httpx_http_error(url, "GET", traceback.format_exc())
            return None

    async def run_docker_compose_up(
        self, dynamic_sidecar_endpoint: str, compose_spec: str
    ) -> bool:
        """returns: True if the compose up was submitted correctly"""
        url = get_url(dynamic_sidecar_endpoint, "/v1/containers")
        try:
            response = await self.httpx_client.post(url, data=compose_spec)
            if response.status_code != 200:
                logging.warning(
                    "error during request status=%s, body=%s",
                    response.status_code,
                    response.text,
                )
                return False

            # request was ok
            logger.info("Spec submit result %s", response.text)
            return True
        except httpx.HTTPError:
            log_httpx_http_error(url, "POST", traceback.format_exc())
            return False

    async def run_docker_compose_down(self, dynamic_sidecar_endpoint: str) -> None:
        """runs docker compose down on the started spec """
        url = get_url(dynamic_sidecar_endpoint, "/v1/containers:down")
        try:
            response = await self.httpx_client.post(url)
            if response.status_code != 200:
                logging.warning(
                    "error during request status=%s, body=%s",
                    response.status_code,
                    response.text,
                )
                return

            logger.info("Compose down result %s", response.text)
        except httpx.HTTPError:
            log_httpx_http_error(url, "POST", traceback.format_exc())


async def setup_api_client(app: Application) -> None:
    logger.debug("dynamic-sidecar api client setup")
    app.state.dynamic_sidecar_api_client = DynamicSidecarClient(app)


async def shutdown_api_client(app: Application) -> None:
    logger.debug("dynamic-sidecar api client shutdown")
    dynamic_sidecar_api_client = app.state.dynamic_sidecar_api_client
    await dynamic_sidecar_api_client.close()


def get_api_client(app: Application) -> DynamicSidecarClient:
    return app.state.dynamic_sidecar_api_client


async def update_dynamic_sidecar_health(
    app: Application, input_monitor_data: MonitorData
) -> MonitorData:
    # make a copy of the original
    output_monitor_data = input_monitor_data.copy(deep=True)

    api_client = get_api_client(app)
    service_endpoint = input_monitor_data.dynamic_sidecar.endpoint

    # update service health
    is_healthy = await api_client.is_healthy(service_endpoint)
    output_monitor_data.dynamic_sidecar.is_available = is_healthy

    return output_monitor_data
