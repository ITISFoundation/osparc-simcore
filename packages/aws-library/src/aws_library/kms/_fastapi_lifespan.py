import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from settings_library.kms import KMSSettings
from tenacity.asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_random_exponential

from aws_library.kms._client import SimcoreKMSAPI
from aws_library.kms._errors import KMSNotConnectedError

_logger = logging.getLogger(__name__)


async def _default_create_kms_client(_: FastAPI, settings: KMSSettings) -> SimcoreKMSAPI:
    return await SimcoreKMSAPI.create(settings)


def configure_kms_client(
    app_lifespan: LifespanManager[FastAPI],
    *,
    settings: KMSSettings | None,
    client_name: str,
    app_state_attr: str = "kms_client",
) -> None:
    async def _lifespan(app: FastAPI) -> AsyncIterator[State]:
        setattr(app.state, app_state_attr, None)

        if settings is None:
            _logger.warning("KMS client '%s' is de-activated in the settings", client_name)
            yield {}
            return

        kms_client = None
        try:
            kms_client = await _default_create_kms_client(app, settings)
            async for attempt in AsyncRetrying(
                reraise=True,
                stop=stop_after_delay(120),
                wait=wait_random_exponential(max=30),
                before_sleep=before_sleep_log(_logger, logging.WARNING),
            ):
                with attempt:
                    connected = await kms_client.ping()
                    if not connected:
                        raise KMSNotConnectedError

            setattr(app.state, app_state_attr, kms_client)
            yield {}
        finally:
            if kms_client is not None:
                await kms_client.close()

    app_lifespan.add(_lifespan)
