import logging
import urllib.parse
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, status
from models_library.services import ServiceKey, ServiceVersion
from models_library.services_resources import ServiceResourcesDict
from models_library.users import UserID
from pydantic import TypeAdapter
from servicelib.fastapi.tracing import setup_httpx_client_tracing
from settings_library.catalog import CatalogSettings
from settings_library.tracing import TracingSettings

from ..utils.client_decorators import handle_errors, handle_retry

logger = logging.getLogger(__name__)


def setup(
    app: FastAPI,
    catalog_settings: CatalogSettings | None,
    tracing_settings: TracingSettings | None,
) -> None:

    if not catalog_settings:
        catalog_settings = CatalogSettings()

    async def on_startup() -> None:
        client = httpx.AsyncClient(
            base_url=f"{catalog_settings.api_base_url}",
            timeout=app.state.settings.CLIENT_REQUEST.HTTP_CLIENT_REQUEST_TOTAL_TIMEOUT,
        )
        if tracing_settings:
            setup_httpx_client_tracing(client=client)

        CatalogClient.create(
            app,
            client=client,
        )
        logger.debug("created client for catalog: %s", catalog_settings.api_base_url)

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
        assert type(app.state.catalog_client) == CatalogClient  # nosec
        return app.state.catalog_client

    @handle_errors("Catalog", logger)
    @handle_retry(logger)
    async def request(self, method: str, tail_path: str, **kwargs) -> httpx.Response:
        return await self.client.request(method, tail_path, **kwargs)

    async def get_service(
        self,
        user_id: UserID,
        service_key: ServiceKey,
        service_version: ServiceVersion,
        product_name: str,
    ) -> dict[str, Any]:
        resp = await self.request(
            "GET",
            f"/services/{urllib.parse.quote( service_key, safe='')}/{service_version}",
            params={"user_id": user_id},
            headers={"X-Simcore-Products-Name": product_name},
        )
        resp.raise_for_status()
        if resp.status_code == status.HTTP_200_OK:
            json_response: dict[str, Any] = resp.json()
            return json_response
        raise HTTPException(status_code=resp.status_code, detail=resp.content)

    async def get_service_resources(
        self, user_id: UserID, service_key: ServiceKey, service_version: ServiceVersion
    ) -> ServiceResourcesDict:
        resp = await self.request(
            "GET",
            f"/services/{urllib.parse.quote( service_key, safe='')}/{service_version}/resources",
            params={"user_id": user_id},
        )
        resp.raise_for_status()
        if resp.status_code == status.HTTP_200_OK:
            json_response: ServiceResourcesDict = TypeAdapter(
                ServiceResourcesDict
            ).validate_python(resp.json())
            return json_response
        raise HTTPException(status_code=resp.status_code, detail=resp.content)

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
            json_response: dict[str, Any] = resp.json()
            return json_response
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
