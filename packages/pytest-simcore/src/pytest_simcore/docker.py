import asyncio
import contextlib
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager

import aiodocker
import pytest


@contextlib.asynccontextmanager
async def _pause_container(
    async_docker_client: aiodocker.Docker, container_name: str
) -> AsyncIterator[None]:
    containers = await async_docker_client.containers.list(
        filters={"name": [f"{container_name}."]}
    )
    await asyncio.gather(*(c.pause() for c in containers))
    # refresh
    container_attrs = await asyncio.gather(*(c.show() for c in containers))
    for container_status in container_attrs:
        assert container_status["State"]["Status"] == "paused"

    yield

    await asyncio.gather(*(c.unpause() for c in containers))
    # refresh
    container_attrs = await asyncio.gather(*(c.show() for c in containers))
    for container_status in container_attrs:
        assert container_status["State"]["Status"] == "running"
    # NOTE: container takes some time to start


@pytest.fixture
async def paused_container() -> Callable[[str], AbstractAsyncContextManager[None]]:
    @contextlib.asynccontextmanager
    async def _(container_name: str) -> AsyncIterator[None]:
        async with aiodocker.Docker() as docker_client, _pause_container(
            docker_client, container_name
        ):
            yield None

    return _
