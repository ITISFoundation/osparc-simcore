""" Module that takes care of communications with director v0 service


"""
import logging
from dataclasses import dataclass

import httpx
from fastapi import FastAPI, HTTPException
from models_library.users import UserID
from servicelib.fastapi.tracing import setup_httpx_client_tracing
from servicelib.logging_utils import log_decorator
from settings_library.s3 import S3Settings
from settings_library.storage import StorageSettings
from settings_library.tracing import TracingSettings

# Module's business logic ---------------------------------------------
from starlette import status

from ..utils.client_decorators import handle_errors, handle_retry
from ..utils.clients import unenvelope_or_raise_error

logger = logging.getLogger(__name__)

# Module's setup logic ---------------------------------------------


def setup(
    app: FastAPI,
    storage_settings: StorageSettings | None,
    tracing_settings: TracingSettings | None,
):

    if not storage_settings:
        storage_settings = StorageSettings()

    def on_startup() -> None:
        client = httpx.AsyncClient(
            base_url=f"{storage_settings.api_base_url}",
            timeout=app.state.settings.CLIENT_REQUEST.HTTP_CLIENT_REQUEST_TOTAL_TIMEOUT,
        )
        if tracing_settings:
            setup_httpx_client_tracing(client=client)
        StorageClient.create(
            app,
            client=client,
        )
        logger.debug("created client for storage: %s", storage_settings.api_base_url)

    async def on_shutdown() -> None:
        client = StorageClient.instance(app).client
        await client.aclose()
        del client

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


@dataclass
class StorageClient:
    client: httpx.AsyncClient

    @classmethod
    def create(cls, app: FastAPI, **kwargs):
        app.state.storage_client = cls(**kwargs)
        return cls.instance(app)

    @classmethod
    def instance(cls, app: FastAPI) -> "StorageClient":
        client: StorageClient = app.state.storage_client
        return client

    @handle_errors("Storage", logger)
    @handle_retry(logger)
    async def request(self, method: str, tail_path: str, **kwargs) -> httpx.Response:
        return await self.client.request(method, tail_path, **kwargs)

    @log_decorator(logger=logger)
    async def get_s3_access(self, user_id: UserID) -> S3Settings:
        resp = await self.request(
            "POST", "/simcore-s3:access", params={"user_id": user_id}
        )
        resp.raise_for_status()
        if resp.status_code == status.HTTP_200_OK:
            return S3Settings.model_validate(unenvelope_or_raise_error(resp))
        raise HTTPException(status_code=resp.status_code, detail=resp.content)
