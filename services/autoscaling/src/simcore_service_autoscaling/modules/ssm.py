import logging
from typing import cast

from aws_library.ssm import SimcoreSSMAPI
from fastapi import FastAPI
from settings_library.ssm import SSMSettings
from tenacity.asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_random_exponential

from ..core.errors import ConfigurationError, SSMNotConnectedError
from ..core.settings import get_application_settings

_logger = logging.getLogger(__name__)


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        app.state.ssm_client = None
        settings: SSMSettings | None = get_application_settings(
            app
        ).AUTOSCALING_SSM_ACCESS

        if not settings:
            _logger.warning("SSM client is de-activated in the settings")
            return

        app.state.ssm_client = client = await SimcoreSSMAPI.create(settings)

        async for attempt in AsyncRetrying(
            reraise=True,
            stop=stop_after_delay(120),
            wait=wait_random_exponential(max=30),
            before_sleep=before_sleep_log(_logger, logging.WARNING),
        ):
            with attempt:
                connected = await client.ping()
                if not connected:
                    raise SSMNotConnectedError  # pragma: no cover

    async def on_shutdown() -> None:
        if app.state.ssm_client:
            await cast(SimcoreSSMAPI, app.state.ssm_client).close()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_ssm_client(app: FastAPI) -> SimcoreSSMAPI:
    if not app.state.ssm_client:
        raise ConfigurationError(
            msg="SSM client is not available. Please check the configuration."
        )
    return cast(SimcoreSSMAPI, app.state.ssm_client)
