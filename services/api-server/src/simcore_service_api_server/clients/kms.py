import logging
from collections.abc import AsyncIterator

from aws_library.kms import KMSNotConnectedError, SimcoreKMSAPI
from fastapi import FastAPI, Request
from fastapi_lifespan_manager import LifespanManager, State

from ..core.settings import ApplicationSettings

_logger = logging.getLogger(__name__)


def get_kms_client(request: Request) -> SimcoreKMSAPI | None:
    kms_client: SimcoreKMSAPI | None = request.app.state.kms_client
    return kms_client


def configure_kms(app_lifespan: LifespanManager[FastAPI]) -> None:
    async def _kms_lifespan(app: FastAPI) -> AsyncIterator[State]:
        app.state.kms_client = None
        settings: ApplicationSettings = app.state.settings
        if settings.API_SERVER_KMS is None:
            yield {}
            return

        kms_client: SimcoreKMSAPI | None = None
        try:
            kms_client = await SimcoreKMSAPI.create(settings.API_SERVER_KMS)
            if not await kms_client.ping():
                _logger.error(
                    "Could not reach AWS KMS with the configured API_SERVER_KMS settings "
                    "(unreachable endpoint, wrong key id, or missing permissions). "
                    "Refusing to start since encryption was requested."
                )
                raise KMSNotConnectedError

            app.state.kms_client = kms_client
            yield {}
        finally:
            if kms_client is not None:
                await kms_client.close()

    app_lifespan.add(_kms_lifespan)
