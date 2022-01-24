from contextlib import asynccontextmanager
from typing import AsyncIterator

from ..client_api import DynamicSidecarClient


@asynccontextmanager
async def disabled_directory_watcher(
    dynamic_sidecar_client: DynamicSidecarClient, dynamic_sidecar_endpoint: str
) -> AsyncIterator[None]:
    try:
        # disable file system event watcher while writing
        # to the outputs directory to avoid data being pushed
        # via nodeports upon change
        await dynamic_sidecar_client.service_disable_dir_watcher(
            dynamic_sidecar_endpoint
        )
        yield
    finally:
        # enable file system event watcher so data from outputs
        # can be again synced via nodeports upon change
        await dynamic_sidecar_client.service_enable_dir_watcher(
            dynamic_sidecar_endpoint
        )
