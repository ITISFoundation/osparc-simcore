import logging
import urllib.parse
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, status
from models_library.services import ServiceKey, ServiceVersion
from models_library.users import UserID

from ..core.settings import CatalogSettings
from ..utils.client_decorators import handle_errors, handle_retry
from ..utils.logging_utils import log_decorator

logger = logging.getLogger(__name__)

_MINUTE = 60


def setup(app: FastAPI, settings: CatalogSettings) -> None:
    if not settings:
        settings = CatalogSettings()

    async def on_startup() -> None:
        CatalogClient.create(
            app,
            client=httpx.AsyncClient(
                base_url=f"{settings.endpoint}",
                timeout=app.state.settings.CLIENT_REQUEST.HTTP_CLIENT_REQUEST_TOTAL_TIMEOUT,
            ),
        )
        logger.debug("created client for catalog: %s", settings.endpoint)

        # Here we currently do not ensure the catalog is up on start
        # This will need to be assessed.

    async def on_shutdown() -> None:
        client = CatalogClient.instance(app).client
        await client.aclose()
        del client

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


@dataclass
class CatalogClient:
    client: httpx.AsyncClient

    @classmethod
    def create(cls, app: FastAPI, **kwargs):
        app.state.catalog_client = cls(**kwargs)
        return cls.instance(app)

    @classmethod
    def instance(cls, app: FastAPI) -> "CatalogClient":
        return app.state.catalog_client

    @handle_errors("Catalog", logger)
    @handle_retry(logger)
    async def request(self, method: str, tail_path: str, **kwargs) -> httpx.Response:
        return await self.client.request(method, tail_path, **kwargs)

    @log_decorator(logger=logger)
    async def get_service_specifications(
        self, user_id: UserID, service_key: ServiceKey, service_version: ServiceVersion
    ) -> dict[str, Any]:

        resp = await self.request(
            "GET",
            f"/services/{urllib.parse.quote( service_key, safe='')}/{service_version}/specifications",
            params={"user_id": user_id},
        )
        resp.raise_for_status()
        if resp.status_code == status.HTTP_200_OK:
            return resp.json()
        raise HTTPException(status_code=resp.status_code, detail=resp.content)

    async def is_responsive(self) -> bool:
        try:
            logger.debug("checking catalog is responsive")
            health_check_path: str = "/"
            result = await self.client.get(health_check_path)  # , timeout=1.0)
            result.raise_for_status()
            return True
        except (httpx.HTTPStatusError, httpx.RequestError, httpx.TimeoutException):
            return False
