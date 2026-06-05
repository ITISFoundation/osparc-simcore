import logging
from collections.abc import AsyncIterator
from typing import cast

from aws_library.ssm import SimcoreSSMAPI
from aws_library.ssm._errors import SSMNotConnectedError
from fastapi import FastAPI
from fastapi_lifespan_manager import State
from settings_library.ssm import SSMSettings
from tenacity.asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_random_exponential

from ..core.errors import ConfigurationError
from ..core.settings import get_application_settings

_logger = logging.getLogger(__name__)


async def ssm_lifespan(app: FastAPI) -> AsyncIterator[State]:
    app.state.ssm_client = None
    settings: SSMSettings | None = get_application_settings(app).AUTOSCALING_SSM_ACCESS

    if not settings:
        _logger.warning("SSM client is de-activated in the settings")
        yield {}
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

    try:
        yield {}
    finally:
        if app.state.ssm_client:
            await cast(SimcoreSSMAPI, app.state.ssm_client).close()


def get_ssm_client(app: FastAPI) -> SimcoreSSMAPI:
    if not app.state.ssm_client:
        raise ConfigurationError(msg="SSM client is not available. Please check the configuration.")
    return cast(SimcoreSSMAPI, app.state.ssm_client)
