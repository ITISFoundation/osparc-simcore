import urllib.parse

from common_library.unset import as_dict_exclude_none
from fastapi import status
from httpx import Response
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services_base import ServiceKeyVersion
from models_library.users import UserID
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from servicelib.fastapi.http_client import AttachLifespanMixin
from servicelib.fastapi.http_client_thin import (
    BaseThinClient,
    expect_status,
    retry_on_errors,
)
from yarl import URL


class DirectorV0ThinClient(
    SingletonInAppStateMixin, BaseThinClient, AttachLifespanMixin
):
    app_state_name: str = "director_v0_thin_client"

    @retry_on_errors()
    @expect_status(status.HTTP_200_OK)
    async def get_running_interactive_service_details(
        self, node_id: NodeID
    ) -> Response:
        return await self.client.get(f"/running_interactive_services/{node_id}")

    @retry_on_errors()
    @expect_status(status.HTTP_200_OK)
    async def get_services_labels(self, service: ServiceKeyVersion) -> Response:
        return await self.client.get(
            f"/services/{urllib.parse.quote_plus(service.key)}/{service.version}/labels"
        )

    @retry_on_errors()
    @expect_status(status.HTTP_200_OK)
    async def get_running_interactive_services(
        self, user_id: UserID | None, project_id: ProjectID | None
    ) -> Response:
        request_url = URL("/running_interactive_services").with_query(
            as_dict_exclude_none(user_id=user_id, study_id=project_id)
        )
        return await self.client.get(f"{request_url}")
