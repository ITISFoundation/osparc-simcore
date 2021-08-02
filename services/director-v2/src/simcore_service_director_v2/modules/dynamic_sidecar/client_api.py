import logging
import traceback
from typing import Any, Dict, Optional

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

    # NOTE: Since this module is accesse concurrently and httpx uses Locks
    # interally, it is not possible to share a single client instace.
    # For each request a separate client will be created.
    # The previous implementation (with a shared client) raised
    # RuntimeErrors because resources were already locked.

    def __init__(self, app: FastAPI):
        dynamic_sidecar_settings: DynamicSidecarSettings = (
            app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
        )

        self._app: FastAPI = app
        self._heatlth_request_timeout: httpx.Timeout = httpx.Timeout(1.0, connect=1.0)
        self._base_timeout = httpx.Timeout(
            dynamic_sidecar_settings.DYNAMIC_SIDECAR_API_REQUEST_TIMEOUT,
            connect=dynamic_sidecar_settings.DYNAMIC_SIDECAR_API_CONNECT_TIMEOUT,
        )

    async def is_healthy(self, dynamic_sidecar_endpoint: str) -> bool:
        """returns True if service is UP and running else False"""
        url = get_url(dynamic_sidecar_endpoint, "/health")
        try:
            # this request uses a very short timeout
            async with httpx.AsyncClient(
                timeout=self._heatlth_request_timeout
            ) as client:
                response = await client.get(url=url)
            response.raise_for_status()

            return response.json()["is_healthy"]
        except httpx.HTTPError:
            return False

    async def containers_inspect(
        self, dynamic_sidecar_endpoint: str
    ) -> Optional[Dict[str, Any]]:
        """returns: None in case of error, otherwise a dict will be returned"""
        url = get_url(dynamic_sidecar_endpoint, "/v1/containers")
        try:
            async with httpx.AsyncClient(timeout=self._base_timeout) as client:
                response = await client.get(url=url)
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
            async with httpx.AsyncClient(timeout=self._base_timeout) as client:
                response = await client.get(url=url, params=dict(only_status=True))
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

    async def start_service_creation(
        self, dynamic_sidecar_endpoint: str, compose_spec: str
    ) -> None:
        """returns: True if the compose up was submitted correctly"""
        url = get_url(dynamic_sidecar_endpoint, "/v1/containers")
        try:
            async with httpx.AsyncClient(timeout=self._base_timeout) as client:
                response = await client.post(url, data=compose_spec)
            if response.status_code != 202:
                message = (
                    f"ERROR during service creation request: "
                    f"status={response.status_code}, body={response.text}"
                )
                logging.warning(message)
                raise DynamicSchedulerException(message)

            # request was ok
            logger.info("Spec submit result %s", response.text)
        except httpx.HTTPError as e:
            log_httpx_http_error(url, "POST", traceback.format_exc())
            raise e

    async def begin_service_destruction(self, dynamic_sidecar_endpoint: str) -> None:
        """runs docker compose down on the started spec"""
        url = get_url(dynamic_sidecar_endpoint, "/v1/containers:down")
        try:
            async with httpx.AsyncClient(timeout=self._base_timeout) as client:
                response = await client.post(url)
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


async def shutdown_api_client(app: FastAPI) -> None:  # pylint: disable=unused-argument
    logger.debug("dynamic-sidecar api client shutdown")


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
