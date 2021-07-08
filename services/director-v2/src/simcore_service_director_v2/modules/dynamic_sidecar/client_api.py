import logging
import traceback
from typing import Dict, Optional

import httpx
from fastapi import FastAPI

from ...core.settings import DynamicSidecarSettings
from ...models.schemas.dynamic_services import SchedulerData
from .errors import DynamicSchedulerException

logger = logging.getLogger(__name__)


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

    def __init__(self, app: FastAPI):
        self._app: FastAPI = app
        self._heatlth_request_timeout: httpx.Timeout = httpx.Timeout(1.0, connect=1.0)

        dynamic_sidecar_settings: DynamicSidecarSettings = (
            app.state.settings.dynamic_services.DYNAMIC_SIDECAR
        )

        self.httpx_client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                dynamic_sidecar_settings.DYNAMIC_SIDECAR_API_REQUEST_TIMEOUT,
                connect=dynamic_sidecar_settings.DYNAMIC_SIDECAR_API_CONNECT_TIMEOUT,
            )
        )

    async def close(self):
        await self.httpx_client.aclose()

    async def is_healthy(self, dynamic_sidecar_endpoint: str) -> bool:
        """returns True if service is UP and running else False"""
        url = get_url(dynamic_sidecar_endpoint, "/health")
        try:
            # this request uses a very short timeout
            response = await self.httpx_client.get(
                url=url, timeout=self._heatlth_request_timeout
            )
            response.raise_for_status()

            return response.json()["is_healthy"]
        except httpx.HTTPError:
            return False

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

    async def begin_service_destruction(self, dynamic_sidecar_endpoint: str) -> None:
        """runs docker compose down on the started spec"""
        url = get_url(dynamic_sidecar_endpoint, "/v1/containers:down")
        try:
            response = await self.httpx_client.post(url)
            if response.status_code != 200:
                message = (
                    f"ERROR during service destruction request: "
                    f"status={response.status_code}, body={response.text}"
                )
                logging.warning(message)
                raise DynamicSchedulerException(message)

            logger.info("Compose down result %s", response.text)
        except httpx.HTTPError as e:
            log_httpx_http_error(url, "POST", traceback.format_exc())
            raise e


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
    app: FastAPI, scheduler_data: SchedulerData
) -> None:

    api_client = get_dynamic_sidecar_client(app)
    service_endpoint = scheduler_data.dynamic_sidecar.endpoint

    # update service health
    is_healthy = await api_client.is_healthy(service_endpoint)
    scheduler_data.dynamic_sidecar.is_available = is_healthy
