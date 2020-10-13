import functools
import logging
from contextlib import suppress
from typing import Coroutine, Dict, Optional

from fastapi import FastAPI, HTTPException
from httpx import AsyncClient, Response
import httpx.codes
from starlette import status

from ..core.settings import CatalogSettings

logger = logging.getLogger(__name__)


# TODO: refactor as template

def setup_catalog(app: FastAPI) -> None:
    settings: CatalogSettings = app.state.settings.catalog

    # init client-api
    logger.debug("Setup catalog at %s...", settings.base_url)
    app.state.catalog_api = CatalogApi(
        base_url=settings.base_url, vtag=app.state.settings.catalog.vtag
    )

    # does NOT communicate with catalog service


async def close_catalog(app: FastAPI) -> None:
    with suppress(AttributeError):
        client: AsyncClient = app.state.catalog_api.client
        await client.aclose()
        del app.state.catalog_api

    logger.debug("Catalog client closed successfully")


# API CLASS ---------------------------------------------


def safe_request(request_func: Coroutine):
    """
        Creates a context for safe inter-process communication (IPC)
    """

    @functools.wraps(request_func)
    async def request_wrapper(zelf: "CatalogApi", path: str, *args, **kwargs) -> Dict:
        try:
            normalized_path = path.lstrip("/")

            resp: Response= await request_func(zelf, path=normalized_path, *args, **kwargs)

        except Exception as err:
            logger.exception(
                "Failed request %s to %s%s",
                request_func.__name__,
                zelf.client.base_url,
                normalized_path,
            )
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE) from err

        # get body
        data: Dict = resp.json()

        # translate error
        if httpx.codes.is_server_error(resp.status_code):
            logger.error(
                "catalog error %d [%s]",
                resp.status_code,
                resp.reason_phrase
            )
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE)

        if httpx.codes.is_client_error(resp.status_code):
            raise HTTPException(resp.status_code, detail=resp.reason_phrase)

        return data or {}

    return request_wrapper



class CatalogApi:
    """
    - wrapper around thin-client to simplify catalog's API
    - sets endspoint upon construction
    - MIME type: application/json
    - processes responses, returning data or raising formatted HTTP exception

    SEE services/catalog/src/simcore_service_catalog/api/dependencies/catalog.py
    """

    def __init__(self, base_url: str, vtag: str):
        self.client = AsyncClient(base_url=base_url)
        self.vtag = vtag

    # OPERATIONS
    # TODO: policy to retry if NetworkError/timeout?
    # TODO: add ping to healthcheck

    @safe_request
    async def get(self, path: str, *args, **kwargs) -> Optional[Dict]:
        return await self.client.get(path, *args, **kwargs)
