import logging
from collections.abc import AsyncIterator
from typing import cast

from aws_library.ec2 import SimcoreEC2API
from aws_library.ec2._errors import EC2NotConnectedError
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from settings_library.ec2 import EC2Settings
from tenacity.asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_random_exponential

from ..core.errors import ConfigurationError
from ..core.settings import get_application_settings

logger = logging.getLogger(__name__)


async def _ec2_client_lifespan(app: FastAPI) -> AsyncIterator[State]:
    app.state.ec2_client = None

    settings: EC2Settings | None = get_application_settings(app).CLUSTERS_KEEPER_EC2_ACCESS

    if not settings:
        logger.warning("EC2 client is de-activated in the settings")
        yield {}
        return

    try:
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
                    raise EC2NotConnectedError  # pragma: no cover

        yield {}
    finally:
        if app.state.ec2_client:
            await cast(SimcoreEC2API, app.state.ec2_client).close()


def configure_ec2_client(app_lifespan: LifespanManager[FastAPI]) -> None:
    app_lifespan.add(_ec2_client_lifespan)


def get_ec2_client(app: FastAPI) -> SimcoreEC2API:
    if not app.state.ec2_client:
        raise ConfigurationError(msg="EC2 client is not available. Please check the configuration.")
    return cast(SimcoreEC2API, app.state.ec2_client)
