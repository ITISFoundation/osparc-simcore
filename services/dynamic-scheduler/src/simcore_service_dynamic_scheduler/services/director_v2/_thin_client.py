import datetime
from typing import cast

from common_library.json_serialization import json_dumps
from fastapi import FastAPI, status
from httpx import Response, Timeout
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStart,
)
from models_library.projects_nodes_io import NodeID
from models_library.services_resources import ServiceResourcesDictHelpers
from servicelib.common_headers import (
    X_DYNAMIC_SIDECAR_REQUEST_DNS,
    X_DYNAMIC_SIDECAR_REQUEST_SCHEME,
    X_SIMCORE_USER_AGENT,
)
from servicelib.fastapi.http_client import AttachLifespanMixin
from servicelib.fastapi.http_client_thin import (
    BaseThinClient,
    expect_status,
    retry_on_errors,
)
from servicelib.rabbitmq.rpc_interfaces.dynamic_scheduler.services import (
    DEFAULT_LEGACY_WB_TO_DV2_HTTP_REQUESTS_TIMEOUT_S,
)

from ...core.settings import ApplicationSettings


class DirectorV2ThinClient(BaseThinClient, AttachLifespanMixin):
    def __init__(self, app: FastAPI) -> None:
        settings: ApplicationSettings = app.state.settings
        super().__init__(
            total_retry_interval=DEFAULT_LEGACY_WB_TO_DV2_HTTP_REQUESTS_TIMEOUT_S,
            base_url=settings.DYNAMIC_SCHEDULER_DIRECTOR_V2_SETTINGS.api_base_url,
            default_http_client_timeout=Timeout(
                DEFAULT_LEGACY_WB_TO_DV2_HTTP_REQUESTS_TIMEOUT_S
            ),
            extra_allowed_method_names={"attach_lifespan_to"},
            tracing_settings=settings.DYNAMIC_SCHEDULER_TRACING,
        )

    @retry_on_errors()
    @expect_status(status.HTTP_200_OK)
    async def get_status(self, node_id: NodeID) -> Response:
        return await self.client.get(
            f"/dynamic_services/{node_id}", follow_redirects=True
        )

    @retry_on_errors()
    @expect_status(status.HTTP_201_CREATED)
    async def post_dynamic_service(
        self, dynamic_service_start: DynamicServiceStart
    ) -> Response:
        post_data = {
            "product_name": dynamic_service_start.product_name,
            "can_save": dynamic_service_start.can_save,
            "user_id": dynamic_service_start.user_id,
            "project_id": dynamic_service_start.project_id,
            "key": dynamic_service_start.key,
            "version": dynamic_service_start.version,
            "node_uuid": dynamic_service_start.node_uuid,
            "basepath": f"/x/{dynamic_service_start.node_uuid}",
            "service_resources": ServiceResourcesDictHelpers.create_jsonable(
                dynamic_service_start.service_resources
            ),
            "wallet_info": dynamic_service_start.wallet_info,
            "pricing_info": dynamic_service_start.pricing_info,
            "hardware_info": dynamic_service_start.hardware_info,
        }

        headers = {
            X_DYNAMIC_SIDECAR_REQUEST_DNS: dynamic_service_start.request_dns,
            X_DYNAMIC_SIDECAR_REQUEST_SCHEME: dynamic_service_start.request_scheme,
            X_SIMCORE_USER_AGENT: dynamic_service_start.simcore_user_agent,
        }

        return await self.client.post(
            "/dynamic_services",
            content=json_dumps(post_data),
            headers=headers,
            follow_redirects=True,
        )

    async def delete_dynamic_service(
        self,
        *,
        node_id: NodeID,
        simcore_user_agent: str,
        save_state: bool,
        timeout: datetime.timedelta,
    ) -> Response:
        @retry_on_errors(total_retry_timeout_overwrite=timeout.total_seconds())
        @expect_status(status.HTTP_204_NO_CONTENT)
        async def _(
            self,  # NOTE: required by retry_on_errors
        ) -> Response:
            headers = {X_SIMCORE_USER_AGENT: simcore_user_agent}

            return cast(
                Response,
                await self.client.delete(
                    f"dynamic_services/{node_id}?can_save={f'{save_state}'.lower()}",
                    headers=headers,
                    timeout=timeout.total_seconds(),
                    follow_redirects=True,
                ),
            )

        return await _(self)
