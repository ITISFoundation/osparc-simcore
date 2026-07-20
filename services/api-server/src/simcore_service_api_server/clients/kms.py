from aws_library.kms import SimcoreKMSAPI
from fastapi import FastAPI, Request

from ..core.settings import ApplicationSettings


def get_kms_client(request: Request) -> SimcoreKMSAPI | None:
    kms_client: SimcoreKMSAPI | None = request.app.state.kms_client
    return kms_client


def setup_kms(app: FastAPI) -> None:
    app.state.kms_client = None

    async def _on_startup() -> None:
        settings: ApplicationSettings = app.state.settings
        if settings.API_SERVER_KMS is not None:
            app.state.kms_client = await SimcoreKMSAPI.create(settings.API_SERVER_KMS)

    async def _on_shutdown() -> None:
        if app.state.kms_client is not None:
            await app.state.kms_client.close()

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)
