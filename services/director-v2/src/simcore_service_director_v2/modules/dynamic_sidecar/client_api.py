import json
import logging
import traceback
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI
from starlette import status

from ...core.settings import DynamicSidecarSettings
from ...models.schemas.dynamic_services import SchedulerData
from ...utils.logging_utils import log_decorator
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


def _response_error_message(response: httpx.Response, tag: Optional[str] = None) -> str:
    formatted_tag = f"[during {tag}]" if tag is not None else ""
    return (
        f"Unexpected response {formatted_tag}: status={response.status_code}, "
        f"body={response.text}"
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

        self._client: httpx.AsyncClient = httpx.AsyncClient(
            timeout=httpx.Timeout(
                dynamic_sidecar_settings.DYNAMIC_SIDECAR_API_REQUEST_TIMEOUT,
                connect=dynamic_sidecar_settings.DYNAMIC_SIDECAR_API_CONNECT_TIMEOUT,
            )
        )

        # timeouts
        self._health_request_timeout: httpx.Timeout = httpx.Timeout(1.0, connect=1.0)
        self._save_restore_timeout: httpx.Timeout = httpx.Timeout(
            dynamic_sidecar_settings.DYNAMIC_SIDECAR_API_SAVE_RESTORE_STATE_TIMEOUT,
            connect=dynamic_sidecar_settings.DYNAMIC_SIDECAR_API_CONNECT_TIMEOUT,
        )
        self._restart_containers_timeout: httpx.Timeout = httpx.Timeout(
            dynamic_sidecar_settings.DYNAMIC_SIDECAR_API_RESTART_CONTAINERS_TIMEOUT,
            connect=dynamic_sidecar_settings.DYNAMIC_SIDECAR_API_CONNECT_TIMEOUT,
        )

    async def is_healthy(self, dynamic_sidecar_endpoint: str) -> bool:
        """returns True if service is UP and running else False"""
        url = get_url(dynamic_sidecar_endpoint, "/health")
        try:
            # this request uses a very short timeout
            response = await self._client.get(
                url=url, timeout=self._health_request_timeout
            )
            response.raise_for_status()

            return response.json()["is_healthy"]
        except httpx.HTTPError:
            return False

    @log_decorator(logger=logger)
    async def containers_inspect(self, dynamic_sidecar_endpoint: str) -> Dict[str, Any]:
        """
        returns dict containing docker inspect result form
        all dynamic-sidecar started containers
        """
        url = get_url(dynamic_sidecar_endpoint, f"/{self.API_VERSION}/containers")

        response = await self._client.get(url=url)
        if response.status_code != status.HTTP_200_OK:
            raise DynamicSidecarNetworkError(_response_error_message(response))

        return response.json()

    @log_decorator(logger=logger)
    async def containers_docker_status(
        self, dynamic_sidecar_endpoint: str
    ) -> Dict[str, Dict[str, str]]:
        url = get_url(dynamic_sidecar_endpoint, f"/{self.API_VERSION}/containers")

        response = await self._client.get(url=url, params=dict(only_status=True))
        if response.status_code != status.HTTP_200_OK:
            logging.warning(_response_error_message(response))
            return {}

        return response.json()

    @log_decorator(logger=logger)
    async def start_service_creation(
        self, dynamic_sidecar_endpoint: str, compose_spec: str
    ) -> None:
        """returns: True if the compose up was submitted correctly"""
        url = get_url(dynamic_sidecar_endpoint, f"/{self.API_VERSION}/containers")

        response = await self._client.post(url, data=compose_spec)
        if response.status_code != status.HTTP_202_ACCEPTED:
            raise DynamicSchedulerException(
                _response_error_message(response, tag="service creation")
            )

        # request was ok
        logger.info("Spec submit result %s", response.text)

    @log_decorator(logger=logger)
    async def begin_service_destruction(self, dynamic_sidecar_endpoint: str) -> None:
        """runs docker compose down on the started spec"""
        url = get_url(dynamic_sidecar_endpoint, f"/{self.API_VERSION}/containers:down")

        response = await self._client.post(url)
        if response.status_code != status.HTTP_200_OK:
            raise DynamicSchedulerException(
                _response_error_message(response, tag="service destruction")
            )

        logger.info("Compose down result %s", response.text)

    @log_decorator(logger=logger)
    async def service_save_state(self, dynamic_sidecar_endpoint: str) -> None:
        url = get_url(dynamic_sidecar_endpoint, "/v1/containers/state:save")

        response = await self._client.post(url, timeout=self._save_restore_timeout)
        if response.status_code != status.HTTP_204_NO_CONTENT:
            raise DynamicSchedulerException(
                _response_error_message(response, tag="state saving")
            )

    @log_decorator(logger=logger)
    async def service_restore_state(self, dynamic_sidecar_endpoint: str) -> None:
        url = get_url(dynamic_sidecar_endpoint, "/v1/containers/state:restore")

        response = await self._client.post(url, timeout=self._save_restore_timeout)
        if response.status_code != status.HTTP_204_NO_CONTENT:
            raise DynamicSchedulerException(
                _response_error_message(response, tag="state restore")
            )

    @log_decorator(logger=logger)
    async def service_pull_input_ports(
        self, dynamic_sidecar_endpoint: str, port_keys: Optional[List[str]] = None
    ) -> int:
        port_keys = [] if port_keys is None else port_keys
        url = get_url(dynamic_sidecar_endpoint, "/v1/containers/ports/inputs:pull")

        response = await self._client.post(
            url, json=port_keys, timeout=self._save_restore_timeout
        )
        if response.status_code != status.HTTP_200_OK:
            raise DynamicSchedulerException(
                _response_error_message(response, tag="pull input ports")
            )
        return int(response.text)

    @log_decorator(logger=logger)
    async def service_disable_dir_watcher(self, dynamic_sidecar_endpoint: str) -> None:
        url = get_url(dynamic_sidecar_endpoint, "/v1/containers/directory-watcher")

        response = await self._client.patch(url, json=dict(is_enabled=False))
        if response.status_code != status.HTTP_204_NO_CONTENT:
            raise DynamicSchedulerException(
                _response_error_message(response, tag="disable dir watcher")
            )

    @log_decorator(logger=logger)
    async def service_enable_dir_watcher(self, dynamic_sidecar_endpoint: str) -> None:
        url = get_url(dynamic_sidecar_endpoint, "/v1/containers/directory-watcher")

        response = await self._client.patch(url, json=dict(is_enabled=True))
        if response.status_code != status.HTTP_204_NO_CONTENT:
            raise DynamicSchedulerException(
                _response_error_message(response, tag="enable dir watcher")
            )

    @log_decorator(logger=logger)
    async def service_outputs_create_dirs(
        self, dynamic_sidecar_endpoint: str, outputs_labels: Dict[str, Any]
    ) -> None:
        url = get_url(dynamic_sidecar_endpoint, "/v1/containers/ports/outputs/dirs")

        response = await self._client.post(
            url, json=dict(outputs_labels=outputs_labels)
        )
        if response.status_code != status.HTTP_204_NO_CONTENT:
            raise DynamicSchedulerException(
                _response_error_message(response, tag="output dir creation")
            )

    @log_decorator(logger=logger)
    async def service_pull_output_ports(
        self, dynamic_sidecar_endpoint: str, port_keys: Optional[List[str]] = None
    ) -> int:
        port_keys = [] if port_keys is None else port_keys
        url = get_url(dynamic_sidecar_endpoint, "/v1/containers/ports/outputs:pull")

        response = await self._client.post(
            url, json=port_keys, timeout=self._save_restore_timeout
        )
        if response.status_code != status.HTTP_200_OK:
            raise DynamicSchedulerException(
                _response_error_message(response, tag="output ports pull")
            )
        return int(response.text)

    @log_decorator(logger=logger)
    async def service_push_output_ports(
        self, dynamic_sidecar_endpoint: str, port_keys: Optional[List[str]] = None
    ) -> None:
        port_keys = [] if port_keys is None else port_keys
        url = get_url(dynamic_sidecar_endpoint, "/v1/containers/ports/outputs:push")

        response = await self._client.post(
            url, json=port_keys, timeout=self._save_restore_timeout
        )
        if response.status_code != status.HTTP_204_NO_CONTENT:
            raise DynamicSchedulerException(
                _response_error_message(response, tag="output ports push")
            )

    @log_decorator(logger=logger)
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

        response = await self._client.get(url=url)
        if response.status_code == status.HTTP_404_NOT_FOUND:
            raise EntrypointContainerNotFoundError()
        response.raise_for_status()

        return response.json()

    @log_decorator(logger=logger)
    async def restart_containers(self, dynamic_sidecar_endpoint: str) -> None:
        """
        runs docker-compose stop and docker-compose start in succession
        resulting in a container restart without loosing state
        """
        url = get_url(
            dynamic_sidecar_endpoint, f"/{self.API_VERSION}/containers:restart"
        )

        response = await self._client.post(
            url=url, timeout=self._restart_containers_timeout
        )
        if response.status_code != status.HTTP_204_NO_CONTENT:
            raise DynamicSchedulerException(
                _response_error_message(response, tag="containers restart")
            )


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
