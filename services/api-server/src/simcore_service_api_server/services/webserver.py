import base64
import json
import logging
from typing import Dict, Optional

import attr
from cryptography import fernet
from fastapi import FastAPI, HTTPException
from httpx import AsyncClient, Response, StatusCode
from starlette import status

from ..core.settings import WebServerSettings

logger = logging.getLogger(__name__)


def _get_secret_key(settings: WebServerSettings):
    secret_key_bytes = settings.session_secret_key.get_secret_value().encode("utf-8")
    while len(secret_key_bytes) < 32:
        secret_key_bytes += secret_key_bytes
    secret_key = secret_key_bytes[:32]

    if isinstance(secret_key, str):
        pass
    elif isinstance(secret_key, (bytes, bytearray)):
        secret_key = base64.urlsafe_b64encode(secret_key)
    return secret_key


def setup_webserver(app: FastAPI) -> None:
    settings: WebServerSettings = app.state.settings.webserver

    # normalize & encrypt
    secret_key = _get_secret_key(settings)
    app.state.webserver_fernet = fernet.Fernet(secret_key)

    # init client
    logger.debug("Setup webserver at %s...", settings.base_url)

    client = AsyncClient(base_url=settings.base_url)
    app.state.webserver_client = client

    # TODO: raise if attribute already exists
    # TODO: ping?


async def close_webserver(app: FastAPI) -> None:
    try:
        client: AsyncClient = app.state.webserver_client
        await client.aclose()
        del app.state.webserver_client
    except AttributeError:
        pass
    logger.debug("Webserver closed successfully")


@attr.s(auto_attribs=True)
class AuthSession:
    """
    - wrapper around thin-client to simplify webserver's API
    - sets endspoint upon construction
    - MIME type: application/json
    - processes responses, returning data or raising formatted HTTP exception
    - The lifetime of an AuthSession is ONE request.

    SEE services/api-server/src/simcore_service_api_server/api/dependencies/webserver.py
    """

    client: AsyncClient  # Its lifetime is attached to app
    vtag: str
    session_cookies: Dict = None

    @classmethod
    def create(cls, app: FastAPI, session_cookies: Dict):
        return cls(
            client=app.state.webserver_client,
            vtag=app.state.settings.webserver.vtag,
            session_cookies=session_cookies,
        )

    def _url(self, path: str) -> str:
        return f"/{self.vtag}/{path.lstrip('/')}"

    @classmethod
    def _process(cls, resp: Response) -> Optional[Dict]:
        # enveloped answer
        data, error = None, None
        try:
            body = resp.json()
            data, error = body["data"], body["error"]
        except (json.JSONDecodeError, KeyError):
            logger.warning("Failed to unenvelop webserver response", exc_info=True)

        if StatusCode.is_server_error(resp.status_code):
            logger.error(
                "webserver error %d [%s]: %s",
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
            resp = await self.client.get(url, cookies=self.session_cookies)
        except Exception:
            logger.exception("Failed to get %s", url)
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE)

        return self._process(resp)

    async def put(self, path: str, body: Dict) -> Optional[Dict]:
        url = self._url(path)
        try:
            resp = await self.client.put(url, json=body, cookies=self.session_cookies)
        except Exception:
            logger.exception("Failed to put %s", url)
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE)

        return self._process(resp)
