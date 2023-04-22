""" Module that takes care of communications with director v0 service


"""
import logging
from dataclasses import dataclass

import httpx
from fastapi import FastAPI, HTTPException
from models_library.users import UserID
from servicelib.logging_utils import log_decorator
from settings_library.s3 import S3Settings

# Module's business logic ---------------------------------------------
from starlette import status

from ..core.settings import StorageSettings
from ..utils.client_decorators import handle_errors, handle_retry
from ..utils.clients import unenvelope_or_raise_error

logger = logging.getLogger(__name__)

# Module's setup logic ---------------------------------------------


def setup(app: FastAPI, settings: StorageSettings):
    if not settings:
        settings = StorageSettings()

    def on_startup() -> None:
        StorageClient.create(
            app,
            client=httpx.AsyncClient(
                base_url=f"{settings.endpoint}",
                timeout=app.state.settings.CLIENT_REQUEST.HTTP_CLIENT_REQUEST_TOTAL_TIMEOUT,
            ),
        )
        logger.debug("created client for storage: %s", settings.endpoint)

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
        return app.state.storage_client

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
            return S3Settings.parse_obj(unenvelope_or_raise_error(resp))
        raise HTTPException(status_code=resp.status_code, detail=resp.content)
