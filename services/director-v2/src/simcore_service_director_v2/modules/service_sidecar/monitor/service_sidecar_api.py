import logging
import traceback
from typing import Any, Dict, Optional

import httpx
from aiohttp.web import Application

from ..config import get_settings
from .models import MonitorData

logger = logging.getLogger(__name__)


KEY_SERVICE_SIDECAR_API_CLIENT = f"{__name__}.ServiceSidecarClient"


def get_url(service_sidecar_endpoint: str, postfix: str) -> str:
    """formats and returns an url for the request"""
    url = f"{service_sidecar_endpoint}{postfix}"
    return url


def log_httpx_http_error(url: str, method: str, formatted_traceback: str) -> None:
    # mainly used to debug issues with the API
    logging.warning(
        (
            "%s -> %s generated:\n %s\nThe above logs can safely "
            "be ignored, except when the service-sidecar is failing"
        ),
        method,
        url,
        formatted_traceback,
    )


class ServiceSidecarClient:
    """Will handle connections to the service sidecar"""

    def __init__(self, app: Application):
        self._app = app
        self._heatlth_request_timeout = httpx.Timeout(1.0, connect=1.0)

        service_sidecar_settings = get_settings(app)

        self.httpx_client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                service_sidecar_settings.service_sidecar_api_request_timeout,
                connect=1.0,
            )
        )

    async def close(self):
        await self.httpx_client.aclose()

    async def is_healthy(self, service_sidecar_endpoint: str) -> bool:
        """retruns True if service is UP and running else False"""
        url = get_url(service_sidecar_endpoint, "/health")
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
        return True

    async def containers_inspect(
        self, service_sidecar_endpoint: str
    ) -> Optional[Dict[str, Any]]:
        """returns: None in case of error, otherwise a dict will be returned"""
        url = get_url(service_sidecar_endpoint, "/containers:inspect")
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
        self, service_sidecar_endpoint: str
    ) -> Optional[Dict[str, Dict[str, str]]]:
        """returns: None in case of error, otherwise a dict will be returned"""
        url = get_url(service_sidecar_endpoint, "/containers:docker-status")
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

    async def store_compose_spec(
        self, service_sidecar_endpoint: str, compose_spec: str
    ) -> bool:
        """returns: True if the compose spec was stored"""
        url = get_url(service_sidecar_endpoint, "/compose:store")
        try:
            response = await self.httpx_client.post(url, data=compose_spec)
            if response.status_code != 204:
                logging.warning(
                    "error during request status=%s, body=%s",
                    response.status_code,
                    response.text,
                )
                return False

            return True
        except httpx.HTTPError:
            log_httpx_http_error(url, "POST", traceback.format_exc())
            return False

    async def pull_images(self, service_sidecar_endpoint: str) -> bool:
        """returns True if succeeded to pull images"""
        service_sidecar_settings = get_settings(self._app)
        command_timeout = (
            service_sidecar_settings.service_sidecar_api_request_docker_compose_pull_timeout
        )

        url = get_url(service_sidecar_endpoint, "/compose:pull")
        try:
            response = await self.httpx_client.get(
                url, params=dict(command_timeout=command_timeout)
            )
            if response.status_code != 200:
                logging.warning(
                    "error during request status=%s, body=%s",
                    response.status_code,
                    response.text,
                )
                return False

            # request was ok
            logger.info("Pull images result %s", response.text)
            return True
        except httpx.HTTPError:
            log_httpx_http_error(url, "POST", traceback.format_exc())
            return False

    async def start_or_update_compose_spec(self, service_sidecar_endpoint: str) -> bool:
        """returns: True if the compose spec was applied """
        service_sidecar_settings = get_settings(self._app)
        command_timeout = (
            service_sidecar_settings.service_sidecar_api_request_docker_compose_up_timeout
        )

        url = get_url(service_sidecar_endpoint, "/compose")
        try:
            response = await self.httpx_client.post(
                url, params=dict(command_timeout=command_timeout)
            )
            if response.status_code != 200:
                logging.warning(
                    "error during request status=%s, body=%s",
                    response.status_code,
                    response.text,
                )
                return False

            # request was ok
            logger.info("Applied spec result %s", response.text)
            return True
        except httpx.HTTPError:
            log_httpx_http_error(url, "POST", traceback.format_exc())
            return False

    async def remove_docker_compose_spec(self, service_sidecar_endpoint: str) -> None:
        """runs docker compose down on the started spec """
        url = get_url(service_sidecar_endpoint, "/compose")
        try:
            response = await self.httpx_client.delete(url)
            if response.status_code != 200:
                logging.warning(
                    "error during request status=%s, body=%s",
                    response.status_code,
                    response.text,
                )
                return

            logger.info("Compose down result %s", response.text)
        except httpx.HTTPError:
            log_httpx_http_error(url, "DELETE", traceback.format_exc())


async def setup_api_client(app: Application) -> None:
    logger.debug("service-sidecar api client setup")
    app.state.service_sidecar_api_client = ServiceSidecarClient(app)


async def shutdown_api_client(app: Application) -> None:
    logger.debug("service-sidecar api client shutdown")
    service_sidecar_client = app.state.service_sidecar_api_client
    await service_sidecar_client.close()


def get_api_client(app: Application) -> ServiceSidecarClient:
    return app.state.service_sidecar_api_client


async def query_service(
    app: Application, input_monitor_data: MonitorData
) -> MonitorData:
    # make a copy of the original
    output_monitor_data = input_monitor_data.copy(deep=True)

    api_client = get_api_client(app)
    service_endpoint = input_monitor_data.service_sidecar.endpoint

    # update service health
    is_healthy = await api_client.is_healthy(service_endpoint)
    output_monitor_data.service_sidecar.is_available = is_healthy

    return output_monitor_data
