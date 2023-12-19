from fastapi import FastAPI, status
from httpx import Response, Timeout
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    CreateDynamicService,
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
from servicelib.json_serialization import json_dumps

from ...core.settings import ApplicationSettings


class DirectorV2ThinClient(BaseThinClient, AttachLifespanMixin):
    def __init__(self, app: FastAPI) -> None:
        settings: ApplicationSettings = app.state.settings

        super().__init__(
            request_timeout=10,
            base_url=settings.DYNAMIC_SCHEDULER_DIRECTOR_V2_SETTINGS.api_base_url,
            timeout=Timeout(10),
            extra_allowed_method_names={"attach_lifespan_to"},
        )

    @retry_on_errors
    @expect_status(status.HTTP_200_OK)
    async def get_status(self, node_id: NodeID) -> Response:
        return await self.client.get(
            f"/dynamic_services/{node_id}", follow_redirects=True
        )

    @retry_on_errors
    @expect_status(status.HTTP_201_CREATED)
    async def post_dynamic_service(
        self, create_dynamic_service: CreateDynamicService
    ) -> Response:
        post_data = {
            "product_name": create_dynamic_service.product_name,
            "can_save": create_dynamic_service.can_save,
            "user_id": create_dynamic_service.user_id,
            "project_id": create_dynamic_service.project_id,
            "key": create_dynamic_service.key,
            "version": create_dynamic_service.version,
            "node_uuid": create_dynamic_service.node_uuid,
            "basepath": f"/x/{create_dynamic_service.node_uuid}",
            "service_resources": ServiceResourcesDictHelpers.create_jsonable(
                create_dynamic_service.service_resources
            ),
            "wallet_info": create_dynamic_service.wallet_info,
            "pricing_info": create_dynamic_service.pricing_info,
            "hardware_info": create_dynamic_service.hardware_info,
        }

        headers = {
            X_DYNAMIC_SIDECAR_REQUEST_DNS: create_dynamic_service.request_dns,
            X_DYNAMIC_SIDECAR_REQUEST_SCHEME: create_dynamic_service.request_scheme,
            X_SIMCORE_USER_AGENT: create_dynamic_service.simcore_user_agent,
        }

        return await self.client.post(
            "/dynamic_services",
            content=json_dumps(post_data),
            headers=headers,
            follow_redirects=True,
        )
