import logging
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Awaitable, Dict, Optional, Type

logger = logging.getLogger(__name__)


@dataclass
class ComputationalSidecar:
    service_key: str
    service_version: str
    input_data: Dict[str, Any]

    async def _pre_process(self) -> None:
        # docker pull image
        # download input data
        # prepare volume with data
        pass

    async def _post_process(self) -> None:
        # get data out of volume
        # format output data
        # upload data if needed
        pass

    async def run(self) -> Dict[str, Any]:
        await self._pre_process()
        await self._post_process()
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
