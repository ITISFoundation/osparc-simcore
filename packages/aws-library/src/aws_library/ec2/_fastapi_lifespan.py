import logging
from collections.abc import AsyncIterator, Awaitable, Callable

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from settings_library.ec2 import EC2Settings
from tenacity.asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_random_exponential

from aws_library.ec2._client import SimcoreEC2API
from aws_library.ec2._errors import EC2NotConnectedError

_logger = logging.getLogger(__name__)

type EC2ClientFactory = Callable[[FastAPI, EC2Settings], Awaitable[SimcoreEC2API]]


async def _default_create_ec2_client(_: FastAPI, settings: EC2Settings) -> SimcoreEC2API:
    return await SimcoreEC2API.create(settings)


def configure_ec2_client(
    app_lifespan: LifespanManager[FastAPI],
    *,
    settings: EC2Settings | None,
    client_name: str,
    app_state_attr: str = "ec2_client",
    client_factory: EC2ClientFactory | None = None,
) -> None:
    async def _lifespan(app: FastAPI) -> AsyncIterator[State]:
        setattr(app.state, app_state_attr, None)

        if settings is None:
            _logger.warning("EC2 client '%s' is de-activated in the settings", client_name)
            yield {}
            return

        ec2_client: SimcoreEC2API | None = None
        try:
            ec2_client = await (client_factory or _default_create_ec2_client)(app, settings)
            async for attempt in AsyncRetrying(
                reraise=True,
                stop=stop_after_delay(120),
                wait=wait_random_exponential(max=30),
                before_sleep=before_sleep_log(_logger, logging.WARNING),
            ):
                with attempt:
                    connected = await ec2_client.ping()
                    if not connected:
                        raise EC2NotConnectedError

            setattr(app.state, app_state_attr, ec2_client)
            yield {}
        finally:
            if ec2_client is not None:
                await ec2_client.close()

    app_lifespan.add(_lifespan)
