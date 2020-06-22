import base64
import logging

from cryptography import fernet
from fastapi import FastAPI
from httpx import AsyncClient

from ..core.settings import WebServerSettings

logger = logging.getLogger(__name__)


# TODO: create client setup with all info inside


def _get_secret_key(settings: WebServerSettings):
    secret_key_bytes = settings.session_secret_key.get_secret_value().encode("utf-8")
    while len(secret_key_bytes) < 32:
        secret_key_bytes += secret_key_bytes
    secret_key = secret_key_bytes[:32]

    if isinstance(secret_key, str):
        pass
    elif isinstance(secret_key, (bytes, bytearray)):
        secret_key = base64.urlsafe_b64encode(secret_key)
    return secret_key


def setup_webserver(app: FastAPI) -> None:
    settings: WebServerSettings = app.state.settings.webserver

    # normalize & encrypt
    secret_key = _get_secret_key(settings)
    app.state.webserver_fernet = fernet.Fernet(secret_key)

    # init client
    logger.debug(f"Setup webserver at {settings.base_url}...")

    client = AsyncClient(base_url=settings.base_url)
    app.state.webserver_client = client

    # TODO: raise if attribute already exists
    # TODO: ping?


async def close_webserver(app: FastAPI) -> None:
    try:
        client: AsyncClient = app.state.webserver_client
        await client.aclose()
        del app.state.webserver_client
    except AttributeError:
        pass
    logger.debug("Webserver closed successfully")


def get_webserver_client(app: FastAPI) -> AsyncClient:
    return app.state.webserver_client
