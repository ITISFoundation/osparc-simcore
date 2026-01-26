import logging
from typing import cast

import aiodocker
from fastapi import FastAPI
from servicelib.fastapi.docker import get_remote_docker_client
from tenacity.asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_random_exponential

from ..core.settings import ApplicationSettings

logger = logging.getLogger(__name__)


class AutoscalingDocker(aiodocker.Docker):
    async def ping(self) -> bool:
        try:
            await self.version()
            return True
        except Exception:  # pylint: disable=broad-except
            return False


def setup(app: FastAPI) -> None:
    settings: ApplicationSettings = app.state.settings

    async def on_startup() -> None:
        # Get the remote docker client configured by servicelib
        if settings.AUTOSCALING_DOCKER_API_PROXY:
            remote_client = get_remote_docker_client(app)

            # Wrap it with AutoscalingDocker to add the ping method
            client = AutoscalingDocker(
                url=remote_client.docker_host,
                connector=remote_client.connector,
                session=remote_client.session,
            )
        else:
            # Local docker client
            client = AutoscalingDocker()
        app.state.docker_client = client

        async for attempt in AsyncRetrying(
            reraise=True,
            stop=stop_after_delay(120),
            wait=wait_random_exponential(max=30),
            before_sleep=before_sleep_log(logger, logging.WARNING),
        ):
            with attempt:
                # this will raise if the connection is not working
                await client.version()

    async def on_shutdown() -> None:
        if app.state.docker_client:
            await cast(AutoscalingDocker, app.state.docker_client).close()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_docker_client(app: FastAPI) -> AutoscalingDocker:
    return cast(AutoscalingDocker, app.state.docker_client)
