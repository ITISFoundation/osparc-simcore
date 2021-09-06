import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Dict

logger = logging.getLogger(__name__)


@dataclass
class ComputationalSidecar:
    service_key: str
    service_version: str
    input_data: Dict[str, Any]

    async def _pre_process(self):
        # docker pull image
        # download input data
        # prepare volume with data
        pass

    async def _post_process(self):
        # get data out of volume
        # format output data
        # upload data if needed
        pass

    async def run(self) -> Dict[str, Any]:
        await self._pre_process()
        await self._post_process()
        return {}

    async def __aenter__(self, *args, **kwargs):
        instance = ComputationalSidecar(*args, **kwargs)

        return instance

    async def __aexit__(self, exc_type, exc, tb):
        pass
