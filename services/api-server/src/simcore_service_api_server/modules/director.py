import logging

import httpx
from fastapi import FastAPI

from ..core.settings import DirectorV2Settings
from ..utils.client_base import BaseServiceClientApi
from ..utils.client_decorators import JsonDataType, handle_errors, handle_retry

logger = logging.getLogger(__name__)

# Module's setup logic ---------------------------------------------


def setup(app: FastAPI, settings: DirectorV2Settings) -> None:
    if not settings:
        settings = DirectorV2Settings()

    def on_startup() -> None:
        logger.debug("Setup %s at %s...", __name__, settings.base_url)
        DirectorApi.create(
            app,
            client=httpx.AsyncClient(base_url=settings.base_url),
            service_name="director",
        )

    async def on_shutdown() -> None:
        client = DirectorApi.get_instance(app)
        if client:
            await client.aclose()
        logger.debug("%s client closed successfully", __name__)

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


# API CLASS ---------------------------------------------


class DirectorApi(BaseServiceClientApi):

    # OPERATIONS
    # TODO: add ping to healthcheck

    @handle_errors("director", logger, return_json=True)
    @handle_retry(logger)
    async def get(self, path: str, *args, **kwargs) -> JsonDataType:
        return await self.client.get(path, *args, **kwargs)
