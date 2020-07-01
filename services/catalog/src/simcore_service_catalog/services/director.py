import json
import logging
from typing import Dict, Optional

import attr
from fastapi import FastAPI, HTTPException
from starlette import status

from httpx import AsyncClient, Response, StatusCode

from ..core.settings import DirectorSettings

logger = logging.getLogger(__name__)


def setup_director(app: FastAPI) -> None:
    settings: DirectorSettings = app.state.settings.director

    # init client
    logger.debug("Setup director at %s...", settings.base_url)

    client = AsyncClient(base_url=settings.base_url)
    app.state.director_client = client

    # TODO: raise if attribute already exists
    # TODO: ping?


async def close_director(app: FastAPI) -> None:
    try:
        client: AsyncClient = app.state.director_client
        await client.aclose()
        del app.state.director_client
    except AttributeError:
        pass
    logger.debug("Director client closed successfully")


@attr.s(auto_attribs=True)
class AuthSession:
    """
    - wrapper around thin-client to simplify director's API
    - sets endspoint upon construction
    - MIME type: application/json
    - processes responses, returning data or raising formatted HTTP exception
    - The lifetime of an AuthSession is ONE request.

    SEE services/catalog/src/simcore_service_catalog/api/dependencies/director.py
    """

    client: AsyncClient  # Its lifetime is attached to app
    vtag: str

    @classmethod
    def create(cls, app: FastAPI):
        return cls(
            client=app.state.director_client, vtag=app.state.settings.director.vtag,
        )

    def _url(self, path: str) -> str:
        return f"/{self.vtag}/{path.lstrip('/')}"

    @classmethod
    def _process(cls, resp: Response) -> Optional[Dict]:
        # enveloped answer
        data, error = None, None
        try:
            body = resp.json()
            if "data" in body:
                data = body["data"]
            if "error" in body:
                error = body["error"]
        except (json.JSONDecodeError, KeyError):
            logger.warning("Failed to unenvelop director response", exc_info=True)

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

        return data

    # OPERATIONS
    # TODO: refactor and code below
    # TODO: policy to retry if NetworkError/timeout?
    # TODO: add ping to healthcheck

    async def get(self, path: str) -> Optional[Dict]:
        url = self._url(path)
        try:
            resp = await self.client.get(url)
        except Exception:
            logger.exception("Failed to get %s", url)
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE)

        return self._process(resp)

    async def put(self, path: str, body: Dict) -> Optional[Dict]:
        url = self._url(path)
        try:
            resp = await self.client.put(url, json=body)
        except Exception:
            logger.exception("Failed to put %s", url)
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE)

        return self._process(resp)
