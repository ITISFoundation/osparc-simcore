import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from settings_library.ssm import SSMSettings
from tenacity.asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_random_exponential

from aws_library.ssm._client import SimcoreSSMAPI
from aws_library.ssm._errors import SSMNotConnectedError

_logger = logging.getLogger(__name__)


async def _default_create_ssm_client(_: FastAPI, settings: SSMSettings) -> SimcoreSSMAPI:
    return await SimcoreSSMAPI.create(settings)


def configure_ssm_client(
    app_lifespan: LifespanManager[FastAPI],
    *,
    settings: SSMSettings | None,
    client_name: str,
    app_state_attr: str = "ssm_client",
) -> None:
    async def _lifespan(app: FastAPI) -> AsyncIterator[State]:
        setattr(app.state, app_state_attr, None)

        if settings is None:
            _logger.warning("SSM client '%s' is de-activated in the settings", client_name)
            yield {}
            return

        ssm_client = None
        try:
            ssm_client = await _default_create_ssm_client(app, settings)
            async for attempt in AsyncRetrying(
                reraise=True,
                stop=stop_after_delay(120),
                wait=wait_random_exponential(max=30),
                before_sleep=before_sleep_log(_logger, logging.WARNING),
            ):
                with attempt:
                    connected = await ssm_client.ping()
                    if not connected:
                        raise SSMNotConnectedError

            setattr(app.state, app_state_attr, ssm_client)
            yield {}
        finally:
            if ssm_client is not None:
                await ssm_client.close()

    app_lifespan.add(_lifespan)
