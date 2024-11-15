import json
from typing import Any

from fastapi import FastAPI, status
from httpx import Response, Timeout
from models_library.services_creation import CreateServiceMetricsAdditionalParams
from models_library.sidecar_volumes import VolumeCategory, VolumeStatus
from pydantic import AnyHttpUrl
from servicelib.docker_constants import SUFFIX_EGRESS_PROXY_NAME
from servicelib.fastapi.http_client_thin import (
    BaseThinClient,
    expect_status,
    retry_on_errors,
)
from settings_library.tracing import TracingSettings

from ....core.dynamic_services_settings.scheduler import (
    DynamicServicesSchedulerSettings,
)


class ThinSidecarsClient(BaseThinClient):  # pylint: disable=too-many-public-methods
    """
    NOTE: all calls can raise the following errors.
    - `UnexpectedStatusError`
    - `ClientHttpError` wraps httpx.HttpError errors
    """

    API_VERSION = "v1"

    def __init__(self, app: FastAPI):
        scheduler_settings: DynamicServicesSchedulerSettings = (
            app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER
        )
        tracing_settings: TracingSettings | None = (
            app.state.settings.DIRECTOR_V2_TRACING
        )

        # timeouts
        self._health_request_timeout = Timeout(1.0, connect=1.0)
        self._save_restore_timeout = Timeout(
            scheduler_settings.DYNAMIC_SIDECAR_API_SAVE_RESTORE_STATE_TIMEOUT.total_seconds(),
            connect=scheduler_settings.DYNAMIC_SIDECAR_API_CONNECT_TIMEOUT,
        )
        self._restart_containers_timeout = Timeout(
            scheduler_settings.DYNAMIC_SIDECAR_API_RESTART_CONTAINERS_TIMEOUT,
            connect=scheduler_settings.DYNAMIC_SIDECAR_API_CONNECT_TIMEOUT,
        )
        self._attach_detach_network_timeout = Timeout(
            scheduler_settings.DYNAMIC_SIDECAR_PROJECT_NETWORKS_ATTACH_DETACH_S,
            connect=scheduler_settings.DYNAMIC_SIDECAR_API_CONNECT_TIMEOUT,
        )

        super().__init__(
            total_retry_interval=scheduler_settings.DYNAMIC_SIDECAR_CLIENT_REQUEST_TIMEOUT_S,
            default_http_client_timeout=Timeout(
                scheduler_settings.DYNAMIC_SIDECAR_API_REQUEST_TIMEOUT,
                connect=scheduler_settings.DYNAMIC_SIDECAR_API_CONNECT_TIMEOUT,
            ),
            tracing_settings=tracing_settings,
        )

    def _get_url(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        postfix: str,
        *,
        no_api_version: bool = False,
    ) -> str:
        """formats and returns an url for the request"""
        api_version = "" if no_api_version else f"{self.API_VERSION}/"
        return f"{dynamic_sidecar_endpoint}{api_version}{postfix}"

    async def _get_health_common(
        self, dynamic_sidecar_endpoint: AnyHttpUrl
    ) -> Response:
        url = self._get_url(dynamic_sidecar_endpoint, "health", no_api_version=True)
        return await self.client.get(url, timeout=self._health_request_timeout)

    @retry_on_errors()
    @expect_status(status.HTTP_200_OK)
    async def get_health(self, dynamic_sidecar_endpoint: AnyHttpUrl) -> Response:
        return await self._get_health_common(dynamic_sidecar_endpoint)

    @expect_status(status.HTTP_200_OK)
    async def get_health_no_retry(
        self, dynamic_sidecar_endpoint: AnyHttpUrl
    ) -> Response:
        return await self._get_health_common(dynamic_sidecar_endpoint)

    @retry_on_errors()
    @expect_status(status.HTTP_200_OK)
    async def get_containers(
        self, dynamic_sidecar_endpoint: AnyHttpUrl, *, only_status: bool
    ) -> Response:
        url = self._get_url(dynamic_sidecar_endpoint, "containers")
        return await self.client.get(url, params={"only_status": only_status})

    @retry_on_errors()
    @expect_status(status.HTTP_204_NO_CONTENT)
    async def patch_containers_ports_io(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        *,
        enable_outputs: bool,
        enable_inputs: bool,
    ) -> Response:
        url = self._get_url(dynamic_sidecar_endpoint, "containers/ports/io")
        return await self.client.patch(
            url, json={"enable_outputs": enable_outputs, "enable_inputs": enable_inputs}
        )

    @retry_on_errors()
    @expect_status(status.HTTP_204_NO_CONTENT)
    async def post_containers_ports_outputs_dirs(
        self, dynamic_sidecar_endpoint: AnyHttpUrl, *, outputs_labels: dict[str, Any]
    ) -> Response:
        url = self._get_url(dynamic_sidecar_endpoint, "containers/ports/outputs/dirs")
        return await self.client.post(url, json={"outputs_labels": outputs_labels})

    @retry_on_errors()
    @expect_status(status.HTTP_200_OK)
    async def get_containers_name(
        self, dynamic_sidecar_endpoint: AnyHttpUrl, *, dynamic_sidecar_network_name: str
    ) -> Response:
        filters = json.dumps(
            {
                "network": dynamic_sidecar_network_name,
                "exclude": SUFFIX_EGRESS_PROXY_NAME,
            }
        )
        url = self._get_url(
            dynamic_sidecar_endpoint, f"containers/name?filters={filters}"
        )
        return await self.client.get(url=url)

    @retry_on_errors()
    @expect_status(status.HTTP_204_NO_CONTENT)
    async def post_containers_networks_attach(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        *,
        container_id: str,
        network_id: str,
        network_aliases: list[str],
    ) -> Response:
        url = self._get_url(
            dynamic_sidecar_endpoint, f"containers/{container_id}/networks:attach"
        )
        return await self.client.post(
            url,
            json={"network_id": network_id, "network_aliases": network_aliases},
            timeout=self._attach_detach_network_timeout,
        )

    @retry_on_errors()
    @expect_status(status.HTTP_204_NO_CONTENT)
    async def post_containers_networks_detach(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        *,
        container_id: str,
        network_id: str,
    ) -> Response:
        url = self._get_url(
            dynamic_sidecar_endpoint, f"containers/{container_id}/networks:detach"
        )
        return await self.client.post(
            url,
            json={"network_id": network_id},
            timeout=self._attach_detach_network_timeout,
        )

    @retry_on_errors()
    @expect_status(status.HTTP_202_ACCEPTED)
    async def post_containers_compose_spec(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        *,
        compose_spec: str,
    ) -> Response:
        url = self._get_url(dynamic_sidecar_endpoint, "containers/compose-spec")
        return await self.client.post(url, json={"docker_compose_yaml": compose_spec})

    @retry_on_errors()
    @expect_status(status.HTTP_202_ACCEPTED)
    async def post_containers_tasks(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        *,
        metrics_params: CreateServiceMetricsAdditionalParams,
    ) -> Response:
        url = self._get_url(dynamic_sidecar_endpoint, "containers")
        return await self.client.post(
            url, json={"metrics_params": metrics_params.model_dump()}
        )

    @retry_on_errors()
    @expect_status(status.HTTP_202_ACCEPTED)
    async def post_containers_tasks_down(
        self, dynamic_sidecar_endpoint: AnyHttpUrl
    ) -> Response:
        url = self._get_url(dynamic_sidecar_endpoint, "containers:down")
        return await self.client.post(url)

    @retry_on_errors()
    @expect_status(status.HTTP_202_ACCEPTED)
    async def post_containers_tasks_state_restore(
        self, dynamic_sidecar_endpoint: AnyHttpUrl
    ) -> Response:
        url = self._get_url(dynamic_sidecar_endpoint, "containers/state:restore")
        return await self.client.post(url)

    @retry_on_errors()
    @expect_status(status.HTTP_202_ACCEPTED)
    async def post_containers_tasks_state_save(
        self, dynamic_sidecar_endpoint: AnyHttpUrl
    ) -> Response:
        url = self._get_url(dynamic_sidecar_endpoint, "containers/state:save")
        return await self.client.post(url)

    @retry_on_errors()
    @expect_status(status.HTTP_202_ACCEPTED)
    async def post_containers_images_pull(
        self, dynamic_sidecar_endpoint: AnyHttpUrl
    ) -> Response:
        url = self._get_url(dynamic_sidecar_endpoint, "containers/images:pull")
        return await self.client.post(url)

    @retry_on_errors()
    @expect_status(status.HTTP_202_ACCEPTED)
    async def post_containers_tasks_ports_inputs_pull(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        port_keys: list[str] | None = None,
    ) -> Response:
        port_keys = [] if port_keys is None else port_keys
        url = self._get_url(dynamic_sidecar_endpoint, "containers/ports/inputs:pull")
        return await self.client.post(url, json=port_keys)

    @retry_on_errors()
    @expect_status(status.HTTP_202_ACCEPTED)
    async def post_containers_tasks_ports_outputs_pull(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        port_keys: list[str] | None = None,
    ) -> Response:
        port_keys = [] if port_keys is None else port_keys
        url = self._get_url(dynamic_sidecar_endpoint, "containers/ports/outputs:pull")
        return await self.client.post(url, json=port_keys)

    @retry_on_errors()
    @expect_status(status.HTTP_202_ACCEPTED)
    async def post_containers_tasks_ports_outputs_push(
        self, dynamic_sidecar_endpoint: AnyHttpUrl
    ) -> Response:
        url = self._get_url(dynamic_sidecar_endpoint, "containers/ports/outputs:push")
        return await self.client.post(url)

    @retry_on_errors()
    @expect_status(status.HTTP_202_ACCEPTED)
    async def post_containers_tasks_restart(
        self, dynamic_sidecar_endpoint: AnyHttpUrl
    ) -> Response:
        url = self._get_url(dynamic_sidecar_endpoint, "containers:restart")
        return await self.client.post(url)

    @retry_on_errors()
    @expect_status(status.HTTP_204_NO_CONTENT)
    async def put_volumes(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
        volume_category: VolumeCategory,
        volume_status: VolumeStatus,
    ) -> Response:
        url = self._get_url(dynamic_sidecar_endpoint, f"volumes/{volume_category}")

        return await self.client.put(url, json={"status": volume_status})

    @retry_on_errors()
    @expect_status(status.HTTP_200_OK)
    async def proxy_config_load(
        self, proxy_endpoint: AnyHttpUrl, proxy_configuration: dict[str, Any]
    ) -> Response:
        url = self._get_url(proxy_endpoint, "load", no_api_version=True)
        return await self.client.post(url, json=proxy_configuration)

    @retry_on_errors()
    @expect_status(status.HTTP_200_OK)
    async def get_containers_activity(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
    ) -> Response:
        url = self._get_url(dynamic_sidecar_endpoint, "containers/activity")
        return await self.client.get(url)

    @retry_on_errors()
    @expect_status(status.HTTP_204_NO_CONTENT)
    async def post_disk_reserved_free(
        self,
        dynamic_sidecar_endpoint: AnyHttpUrl,
    ) -> Response:
        url = self._get_url(dynamic_sidecar_endpoint, "disk/reserved:free")
        return await self.client.post(url)
