import logging
from typing import cast

from aws_library.ec2.client import SimcoreEC2API
from fastapi import FastAPI
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_random_exponential

from ..core.errors import ConfigurationError, Ec2NotConnectedError
from ..core.settings import EC2ClustersKeeperSettings, get_application_settings

logger = logging.getLogger(__name__)


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        app.state.ec2_client = None

        settings: EC2ClustersKeeperSettings | None = get_application_settings(
            app
        ).CLUSTERS_KEEPER_EC2_ACCESS

        if not settings:
            logger.warning("EC2 client is de-activated in the settings")
            return

        app.state.ec2_client = client = await SimcoreEC2API.create(settings)

        async for attempt in AsyncRetrying(
            reraise=True,
            stop=stop_after_delay(120),
            wait=wait_random_exponential(max=30),
            before_sleep=before_sleep_log(logger, logging.WARNING),
        ):
            with attempt:
                connected = await client.ping()
                if not connected:
                    raise Ec2NotConnectedError  # pragma: no cover

    async def on_shutdown() -> None:
        if app.state.ec2_client:
            await cast(SimcoreEC2API, app.state.ec2_client).close()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_ec2_client(app: FastAPI) -> ClustersKeeperEC2:
    if not app.state.ec2_client:
        raise ConfigurationError(
            msg="EC2 client is not available. Please check the configuration."
        )
    return cast(ClustersKeeperEC2, app.state.ec2_client)
