import logging
from collections.abc import AsyncIterator
from typing import cast

import aiodocker
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from tenacity.asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_random_exponential

logger = logging.getLogger(__name__)


class AutoscalingDocker(aiodocker.Docker):
    async def ping(self) -> bool:
        try:
            await self.version()
            return True
        except Exception:  # pylint: disable=broad-except
            return False


async def _docker_lifespan(app: FastAPI) -> AsyncIterator[State]:
    app.state.docker_client = None
    try:
        app.state.docker_client = client = AutoscalingDocker()

        async for attempt in AsyncRetrying(
            reraise=True,
            stop=stop_after_delay(120),
            wait=wait_random_exponential(max=30),
            before_sleep=before_sleep_log(logger, logging.WARNING),
        ):
            with attempt:
                # this will raise if the connection is not working
                await client.version()

        yield {}
    finally:
        if app.state.docker_client:
            await cast(AutoscalingDocker, app.state.docker_client).close()


def configure_docker_client(app_lifespan: LifespanManager[FastAPI]) -> None:
    app_lifespan.add(_docker_lifespan)


def get_docker_client(app: FastAPI) -> AutoscalingDocker:
    return cast(AutoscalingDocker, app.state.docker_client)
