import json
import logging
import traceback
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI
from starlette import status

from ...core.settings import DynamicSidecarSettings
from ...models.schemas.dynamic_services import SchedulerData
from .errors import (
    DynamicSchedulerException,
    DynamicSidecarNetworkError,
    EntrypointContainerNotFoundError,
)

# PC -> SAN improvements to discuss
#
# TODO: Use logger, not logging!
#      - compose error msgs instead of log functions
# TODO: Single instance of httpx client for all requests?: https://www.python-httpx.org/advanced/#why-use-a-client
#      - see services/api-server/src/simcore_service_api_server/utils/client_base.py  (-> move to servicelib/fastapi ?)
# TODO: context to unify session's error handling and logging
# TODO: client function names equal/very similar to server handlers
#

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

    API_VERSION = "v1"

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
        self._save_restore_timeout = httpx.Timeout(
            dynamic_sidecar_settings.DYNAMIC_SIDECAR_API_SAVE_RESTORE_STATE_TIMEOUT,
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

    async def containers_inspect(self, dynamic_sidecar_endpoint: str) -> Dict[str, Any]:
        """
        returns dict containing docker inspect result form
        all dynamic-sidecar started containers
        """
        url = get_url(dynamic_sidecar_endpoint, f"/{self.API_VERSION}/containers")
        try:
            async with httpx.AsyncClient(timeout=self._base_timeout) as client:
                response = await client.get(url=url)
            if response.status_code != status.HTTP_200_OK:
                message = (
                    f"error during request status={response.status_code}, "
                    f"body={response.text}"
                )
                logging.warning(message)
                raise DynamicSidecarNetworkError(message)

            return response.json()
        except httpx.HTTPError:
            log_httpx_http_error(url, "GET", traceback.format_exc())
            raise

    async def containers_docker_status(
        self, dynamic_sidecar_endpoint: str
    ) -> Dict[str, Dict[str, str]]:
        url = get_url(dynamic_sidecar_endpoint, f"/{self.API_VERSION}/containers")
        try:
            async with httpx.AsyncClient(timeout=self._base_timeout) as client:
                response = await client.get(url=url, params=dict(only_status=True))
            if response.status_code != status.HTTP_200_OK:
                logging.warning(
                    "error during request status=%s, body=%s",
                    response.status_code,
                    response.text,
                )
                return {}

            return response.json()
        except httpx.HTTPError:
            log_httpx_http_error(url, "GET", traceback.format_exc())
            raise

    async def start_service_creation(
        self, dynamic_sidecar_endpoint: str, compose_spec: str
    ) -> None:
        """returns: True if the compose up was submitted correctly"""
        url = get_url(dynamic_sidecar_endpoint, f"/{self.API_VERSION}/containers")
        try:
            async with httpx.AsyncClient(timeout=self._base_timeout) as client:
                response = await client.post(url, data=compose_spec)
            if response.status_code != status.HTTP_202_ACCEPTED:
                message = (
                    "ERROR during service creation request: "
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
        url = get_url(dynamic_sidecar_endpoint, f"/{self.API_VERSION}/containers:down")
        try:
            async with httpx.AsyncClient(timeout=self._base_timeout) as client:
                response = await client.post(url)
            if response.status_code != status.HTTP_200_OK:
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

    async def service_save_state(self, dynamic_sidecar_endpoint: str) -> None:
        url = get_url(dynamic_sidecar_endpoint, "/v1/containers/state:save")
        try:
            async with httpx.AsyncClient(timeout=self._save_restore_timeout) as client:
                response = await client.post(url)
            if response.status_code != status.HTTP_204_NO_CONTENT:
                message = (
                    f"ERROR while saving service state: "
                    f"status={response.status_code}, body={response.text}"
                )
                logging.warning(message)
                raise DynamicSchedulerException(message)
        except httpx.HTTPError as e:
            log_httpx_http_error(url, "POST", traceback.format_exc())
            raise e

    async def service_restore_state(self, dynamic_sidecar_endpoint: str) -> None:
        url = get_url(dynamic_sidecar_endpoint, "/v1/containers/state:restore")
        try:
            async with httpx.AsyncClient(timeout=self._save_restore_timeout) as client:
                response = await client.post(url)
            if response.status_code != status.HTTP_204_NO_CONTENT:
                message = (
                    f"ERROR while restoring service state: "
                    f"status={response.status_code}, body={response.text}"
                )
                logging.warning(message)
                raise DynamicSchedulerException(message)
        except httpx.HTTPError:
            log_httpx_http_error(url, "POST", traceback.format_exc())
            raise

    async def service_pull_input_ports(
        self, dynamic_sidecar_endpoint: str, port_keys: Optional[List[str]] = None
    ) -> int:
        port_keys = [] if port_keys is None else port_keys
        url = get_url(dynamic_sidecar_endpoint, "/v1/containers/ports/inputs:pull")
        try:
            async with httpx.AsyncClient(timeout=self._save_restore_timeout) as client:
                response = await client.post(url, json=port_keys)
            if response.status_code != status.HTTP_200_OK:
                message = (
                    f"ERROR while restoring service state: "
                    f"status={response.status_code}, body={response.text}"
                )
                logging.warning(message)
                raise DynamicSchedulerException(message)
            return int(response.text)
        except httpx.HTTPError as e:
            log_httpx_http_error(url, "POST", traceback.format_exc())
            raise e

    async def service_push_output_ports(
        self, dynamic_sidecar_endpoint: str, port_keys: Optional[List[str]] = None
    ) -> None:
        port_keys = [] if port_keys is None else port_keys
        url = get_url(dynamic_sidecar_endpoint, "/v1/containers/ports/outputs:push")
        try:
            async with httpx.AsyncClient(timeout=self._save_restore_timeout) as client:
                response = await client.post(url, json=port_keys)
            if response.status_code != status.HTTP_204_NO_CONTENT:
                message = (
                    f"ERROR while restoring service state: "
                    f"status={response.status_code}, body={response.text}"
                )
                logging.warning(message)
                raise DynamicSchedulerException(message)
        except httpx.HTTPError as e:
            log_httpx_http_error(url, "POST", traceback.format_exc())
            raise e

    async def get_entrypoint_container_name(
        self, dynamic_sidecar_endpoint: str, dynamic_sidecar_network_name: str
    ) -> str:
        """
        While this API raises EntrypointContainerNotFoundError
        it should be called again, because in the menwhile the containers
        might still be starting.
        """
        filters = json.dumps({"network": dynamic_sidecar_network_name})
        url = get_url(
            dynamic_sidecar_endpoint,
            f"/{self.API_VERSION}/containers/name?filters={filters}",
        )
        try:
            async with httpx.AsyncClient(timeout=self._base_timeout) as client:
                response = await client.get(url=url)
                if response.status_code == status.HTTP_404_NOT_FOUND:
                    raise EntrypointContainerNotFoundError()
                response.raise_for_status()

                return response.json()
        except httpx.HTTPError:
            log_httpx_http_error(url, "GET", traceback.format_exc())
            raise


async def setup_api_client(app: FastAPI) -> None:
    logger.debug("dynamic-sidecar api client setup")
    app.state.dynamic_sidecar_api_client = DynamicSidecarClient(app)


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
