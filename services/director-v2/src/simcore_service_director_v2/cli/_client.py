import logging

from fastapi import status
from httpx import AsyncClient, Response, Timeout

from ..modules.dynamic_sidecar.api_client._base import (
    BaseThinClient,
    expect_status,
    retry_on_errors,
)

logger = logging.getLogger(__name__)


class ThinDv2LocalhostClient(BaseThinClient):
    """
    NOTE: all calls can raise the following errors.
    - `UnexpectedStatusError`
    - `ClientHttpError` wraps httpx.HttpError errors
    """

    API_VERSION = "v1"

    def __init__(self):
        self.client = AsyncClient(timeout=Timeout(5))
        self._request_max_retries: int = 3

        # timeouts
        self._health_request_timeout = Timeout(1.0, connect=1.0)
        self._long_running_timeout = Timeout(3600, connect=5)

        self.base_address: str = "http://localhost:8000"

        super().__init__(request_max_retries=self._request_max_retries)

    def _get_url(self, postfix: str) -> str:
        return f"{self.base_address}/v2/dynamic_scheduler{postfix}"

    @retry_on_errors
    @expect_status(status.HTTP_202_ACCEPTED)
    async def delete_service_containers(self, node_uuid: str) -> Response:
        return await self.client.delete(self._get_url(f"/{node_uuid}/containers"))

    @retry_on_errors
    @expect_status(status.HTTP_202_ACCEPTED)
    async def save_service_state(self, node_uuid: str) -> Response:
        return await self.client.post(self._get_url(f"/{node_uuid}/state:save"))

    @retry_on_errors
    @expect_status(status.HTTP_202_ACCEPTED)
    async def push_service_outputs(self, node_uuid: str) -> Response:
        return await self.client.post(self._get_url(f"/{node_uuid}/outputs:push"))

    @retry_on_errors
    @expect_status(status.HTTP_202_ACCEPTED)
    async def delete_service_docker_resources(self, node_uuid: str) -> Response:
        return await self.client.delete(self._get_url(f"/{node_uuid}/docker-resources"))
