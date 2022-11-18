import logging

from fastapi import status
from httpx import AsyncClient, Response, Timeout

from ..modules.dynamic_sidecar.api_client._base import (
    BaseThinClient,
    expect_status,
    retry_on_errors,
)

logger = logging.getLogger(__name__)


class ThinDV2LocalhostClient(BaseThinClient):
    BASE_ADDRESS: str = "http://localhost:8000"

    def __init__(self):
        self.client = AsyncClient(timeout=Timeout(5))

        super().__init__(request_timeout=10)

    def _get_url(self, postfix: str) -> str:
        return f"{self.BASE_ADDRESS}/v2/dynamic_scheduler{postfix}"

    @retry_on_errors
    @expect_status(status.HTTP_204_NO_CONTENT)
    async def toggle_service_observation(
        self, node_uuid: str, *, is_disabled: bool
    ) -> Response:
        return await self.client.patch(
            self._get_url(f"/services/{node_uuid}/observation"),
            json=dict(is_disabled=is_disabled),
        )

    @retry_on_errors
    @expect_status(status.HTTP_202_ACCEPTED)
    async def delete_service_containers(self, node_uuid: str) -> Response:
        return await self.client.delete(
            self._get_url(f"/services/{node_uuid}/containers")
        )

    @retry_on_errors
    @expect_status(status.HTTP_202_ACCEPTED)
    async def save_service_state(self, node_uuid: str) -> Response:
        return await self.client.post(
            self._get_url(f"/services/{node_uuid}/state:save")
        )

    @retry_on_errors
    @expect_status(status.HTTP_202_ACCEPTED)
    async def push_service_outputs(self, node_uuid: str) -> Response:
        return await self.client.post(
            self._get_url(f"/services/{node_uuid}/outputs:push")
        )

    @retry_on_errors
    @expect_status(status.HTTP_202_ACCEPTED)
    async def delete_service_docker_resources(self, node_uuid: str) -> Response:
        return await self.client.delete(
            self._get_url(f"/services/{node_uuid}/docker-resources")
        )
