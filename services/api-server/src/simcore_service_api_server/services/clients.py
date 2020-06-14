from fastapi import FastAPI
from httpx import AsyncClient
from loguru import logger

from ..core.settings import WebServerSettings


def setup_webserver_client(app: FastAPI) -> None:
    settings: WebServerSettings = app.state.settings.webserver
    base_url = f"http://{settings.host}:{settings.port}"
    logger.debug(f"Setup webserver at {base_url}...")

    client = AsyncClient(base_url=base_url)
    app.state.webserver_client = client

    # TODO: raise if attribute already exists
    # TODO: ping?


async def close_webserver_client(app: FastAPI) -> None:
    try:
        client: AsyncClient = app.state.webserver_client
        await client.aclose()
        del app.state.webserver_client
    except AttributeError:
        pass
    logger.debug("Webserver closed successfully")
