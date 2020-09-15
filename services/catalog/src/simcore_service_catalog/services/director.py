import functools
import logging
from contextlib import suppress
from typing import Coroutine, Dict, Optional

from fastapi import FastAPI, HTTPException
from httpx import AsyncClient, Response, StatusCode
from starlette import status

from ..core.settings import DirectorSettings

logger = logging.getLogger(__name__)


def setup_director(app: FastAPI) -> None:
    settings: DirectorSettings = app.state.settings.director

    # init client-api
    logger.debug("Setup director at %s...", settings.base_url)
    app.state.director_api = DirectorApi(
        base_url=settings.base_url, vtag=app.state.settings.director.vtag
    )

    # does NOT communicate with director service


async def close_director(app: FastAPI) -> None:
    with suppress(AttributeError):
        client: AsyncClient = app.state.director_client
        await client.aclose()
        del app.state.director_client

    logger.debug("Director client closed successfully")


# DIRECTOR API CLASS ---------------------------------------------


def safe_request(request_func: Coroutine):
    """
    Creates a context for safe inter-process communication (IPC)
    """

    def _unenvelope_or_raise_error(resp: Response) -> Dict:
        """
        Director responses are enveloped
        If successful response, we un-envelop it and return data as a dict
        If error, it raise an HTTPException
        """
        body = resp.json()

        assert "data" in body or "error" in body  # nosec
        data = body.get("data")
        error = body.get("error")

        if StatusCode.is_server_error(resp.status_code):
            logger.error(
                "director error %d [%s]: %s",
                resp.status_code,
                resp.reason_phrase,
                error,
            )
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE)

        if StatusCode.is_client_error(resp.status_code):
            msg = error or resp.reason_phrase
            raise HTTPException(resp.status_code, detail=msg)

        return data or {}

    @functools.wraps(request_func)
    async def request_wrapper(self: "AuthSession", path: str, *args, **kwargs):
        try:
            normalized_path = path.lstrip("/")
            resp = await request_func(self, path=normalized_path, *args, **kwargs)
        except Exception as err:
            logger.exception("Failed to put %s%s", self.client.base_url, path)
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE) from err

        return _unenvelope_or_raise_error(resp)

    return request_wrapper


class DirectorApi:
    """
    - wrapper around thin-client to simplify director's API
    - sets endspoint upon construction
    - MIME type: application/json
    - processes responses, returning data or raising formatted HTTP exception

    SEE services/catalog/src/simcore_service_catalog/api/dependencies/director.py
    """

    def __init__(self, base_url: str, vtag: str):
        self._client = AsyncClient(base_url=base_url)
        self.vtag = vtag

    # OPERATIONS
    # TODO: policy to retry if NetworkError/timeout?
    # TODO: add ping to healthcheck

    @safe_request
    async def get(self, path: str) -> Optional[Dict]:
        return await self._client.get(path)

    @safe_request
    async def put(self, path: str, body: Dict) -> Optional[Dict]:
        return await self._client.put(path, json=body)
