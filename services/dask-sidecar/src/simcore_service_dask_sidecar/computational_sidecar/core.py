import logging
from dataclasses import dataclass
from pprint import pformat
from types import TracebackType
from typing import Any, Awaitable, Dict, Optional, Type

from aiodocker import Docker

logger = logging.getLogger(__name__)


@dataclass
class ComputationalSidecar:
    service_key: str
    service_version: str
    input_data: Dict[str, Any]

    async def run(self) -> Dict[str, Any]:
        async with Docker() as docker_client:
            # pull the image
            async for pull_progress in docker_client.images.pull(
                f"{self.service_key}:{self.service_version}", stream=True
            ):
                logger.info(
                    "pulling %s:%s: %s",
                    self.service_key,
                    self.service_version,
                    pformat(pull_progress),
                )

            # run the image

        return {}

    async def __aenter__(self) -> "ComputationalSidecar":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> Awaitable[Optional[bool]]:
        ...
