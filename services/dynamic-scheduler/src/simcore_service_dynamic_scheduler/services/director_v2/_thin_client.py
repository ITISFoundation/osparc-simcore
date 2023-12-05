from fastapi import FastAPI, status
from httpx import Response, Timeout
from models_library.projects_nodes_io import NodeID
from servicelib.fastapi.http_client_thin import (
    BaseThinClient,
    expect_status,
    retry_on_errors,
)

from ...core.settings import ApplicationSettings


class DirectorV2ThinClient(BaseThinClient):
    def __init__(self, app: FastAPI) -> None:
        settings: ApplicationSettings = app.state.settings

        super().__init__(
            request_timeout=10,
            base_url=settings.DYNAMIC_SCHEDULER_DIRECTOR_V2_SETTINGS.api_base_url,
            timeout=Timeout(10),
        )

    @retry_on_errors
    @expect_status(status.HTTP_200_OK)
    async def get_status(self, node_id: NodeID) -> Response:
        return await self.client.get(f"/dynamic-services/{node_id}")
