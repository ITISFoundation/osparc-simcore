from requests import Response
from ._thin_client import ThinDynamicSidecarClient
from pydantic import AnyHttpUrl
from httpx import HTTPError
from ..errors import DynamicSidecarUnexpectedResponseStatus
from ....utils.logging_utils import log_decorator
import logging
from typing import Any
from ._errors import UnexpectedStatusError

logger = logging.getLogger(__name__)


class DynamicSidecarClient(ThinDynamicSidecarClient):
    async def is_healthy(self, dynamic_sidecar_endpoint: AnyHttpUrl) -> bool:
        """returns True if service is UP and running else False"""
        try:
            # this request uses a very short timeout
            response = await self.get_health(dynamic_sidecar_endpoint)
            return response.json()["is_healthy"]
        except (HTTPError, DynamicSidecarUnexpectedResponseStatus):
            return False

    @log_decorator(logger=logger)
    async def containers_inspect(
        self, dynamic_sidecar_endpoint: AnyHttpUrl
    ) -> dict[str, Any]:
        """
        returns dict containing docker inspect result form
        all dynamic-sidecar started containers
        """
        response = await self.get_containers(
            dynamic_sidecar_endpoint, only_status=False
        )
        return response.json()

    @log_decorator(logger=logger)
    async def containers_docker_status(
        self, dynamic_sidecar_endpoint: AnyHttpUrl
    ) -> dict[str, dict[str, str]]:
        try:
            response = await self.get_containers(
                dynamic_sidecar_endpoint, only_status=True
            )
            return response.json()
        except UnexpectedStatusError:
            return {}

    @log_decorator(logger=logger)
    async def start_service_creation(
        self, dynamic_sidecar_endpoint: AnyHttpUrl, compose_spec: str
    ) -> None:
        response = await self.post_containers(
            dynamic_sidecar_endpoint, compose_spec=compose_spec
        )
        # request was ok
        logger.info("Spec submit result %s", response.text)
