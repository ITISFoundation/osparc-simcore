import logging
from contextlib import suppress

import httpx
from fastapi import FastAPI
from typing import Dict

from ..core.settings import CatalogSettings
from ..utils.client_decorators import handle_errors, handle_retry, JsonDataType

logger = logging.getLogger(__name__)


def setup(app: FastAPI, settings: CatalogSettings) -> None:
    if not settings:
        settings = CatalogSettings()

    def on_startup() -> None:
        logger.debug("Setup catalog at %s...", settings.base_url)
        app.state.catalog_api = CatalogApi(
            base_url=settings.base_url, vtag=app.state.settings.catalog.vtag
        )

    async def on_shutdown() -> None:
        with suppress(AttributeError):
            client: httpx.AsyncClient = app.state.catalog_api.client
            await client.aclose()
            del app.state.catalog_api
        logger.debug("Catalog client closed successfully")

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


# API CLASS ---------------------------------------------


class CatalogApi:
    """
    - wrapper around thin-client to simplify catalog's API
    - sets endspoint upon construction
    - MIME type: application/json
    - processes responses, returning data or raising formatted HTTP exception

    SEE services/catalog/src/simcore_service_catalog/api/dependencies/catalog.py
    """

    def __init__(self, base_url: str, vtag: str):
        self.client = httpx.AsyncClient(base_url=base_url)
        self.vtag = vtag

    # OPERATIONS
    # TODO: add ping to healthcheck

    @handle_errors("catalog", logger, return_json=True)
    @handle_retry(logger)
    async def get(self, path: str, *args, **kwargs) -> JsonDataType:
        return await self.client.get(path, *args, **kwargs)
