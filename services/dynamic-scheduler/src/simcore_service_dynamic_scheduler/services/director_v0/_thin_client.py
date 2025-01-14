from common_library.unset import as_dict_exclude_none
from fastapi import FastAPI, status
from httpx import Response
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from servicelib.fastapi.http_client import AttachLifespanMixin
from servicelib.fastapi.http_client_thin import (
    BaseThinClient,
    expect_status,
    retry_on_errors,
)
from yarl import URL

from ...core.settings import ApplicationSettings


class DirectorV0ThinClient(
    SingletonInAppStateMixin, BaseThinClient, AttachLifespanMixin
):
    app_state_name: str = "director_v0_thin_client"

    def __init__(self, app: FastAPI) -> None:
        settings: ApplicationSettings = app.state.settings
        assert settings.CLIENT_REQUEST.HTTP_CLIENT_REQUEST_TOTAL_TIMEOUT  # nosec

        super().__init__(
            total_retry_interval=int(
                settings.CLIENT_REQUEST.HTTP_CLIENT_REQUEST_TOTAL_TIMEOUT
            ),
            extra_allowed_method_names={
                "attach_lifespan_to",
                "get_from_app_state",
                "pop_from_app_state",
                "set_to_app_state",
            },
            base_url=settings.DYNAMIC_SCHEDULER_DIRECTOR_V0_SETTINGS.endpoint,
            tracing_settings=settings.DYNAMIC_SCHEDULER_TRACING,
        )

    @retry_on_errors()
    @expect_status(status.HTTP_200_OK)
    async def get_running_interactive_service_details(
        self, node_id: NodeID
    ) -> Response:
        return await self.client.get(f"/running_interactive_services/{node_id}")

    @retry_on_errors()
    @expect_status(status.HTTP_200_OK)
    async def get_running_interactive_services(
        self, user_id: UserID | None, project_id: ProjectID | None
    ) -> Response:
        request_url = URL("/running_interactive_services").with_query(
            as_dict_exclude_none(user_id=user_id, study_id=project_id)
        )
        return await self.client.get(f"{request_url}")
