"""Interface to communicate with Fogbugz API

- Simple client to create cases in Fogbugz
"""

import logging
from typing import Any, Final
from urllib.parse import urljoin

import httpx
from aiohttp import web
from pydantic import AnyUrl, BaseModel, Field
from servicelib.aiohttp import status
from tenacity import (
    retry,
    retry_if_exception_type,
    retry_if_result,
    stop_after_attempt,
    wait_exponential,
)

from .settings import get_plugin_settings

_logger = logging.getLogger(__name__)

_JSON_CONTENT_TYPE = "application/json"
_UNKNOWN_ERROR_MESSAGE = "Unknown error occurred"


class ChatbotQuestionCreate(BaseModel):
    fogbugz_project_id: int = Field(description="Project ID in Fogbugz")
    title: str = Field(description="Case title")
    description: str = Field(description="Case description/first comment")


def _should_retry(response: httpx.Response | None) -> bool:
    if response is None:
        return True
    return (
        response.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR
        or response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    )


class ChatbotRestClient:
    def __init__(self, host: AnyUrl, port: int) -> None:
        self._client = httpx.AsyncClient()
        self.host = host
        self.port = port
        self._base_url = f"{self.host}:{self.port}"

    async def get_settings(self) -> dict[str, Any]:
        """Fetches chatbot settings"""
        url = urljoin(f"{self._base_url}", "/v1/chat/settings")

        @retry(
            retry=(
                retry_if_result(_should_retry)
                | retry_if_exception_type(
                    (
                        httpx.ConnectError,
                        httpx.TimeoutException,
                        httpx.NetworkError,
                        httpx.ProtocolError,
                    )
                )
            ),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )
        async def _request() -> httpx.Response:
            return await self._client.get(url)

        try:
            response = await _request()
            response.raise_for_status()
            response_data: dict[str, Any] = response.json()
            return response_data
        except Exception:
            _logger.error(  # noqa: TRY400
                "Failed to fetch chatbot settings from %s", url
            )
            raise

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup client"""
        await self._client.aclose()


_APPKEY: Final = web.AppKey(ChatbotRestClient.__name__, ChatbotRestClient)


async def setup_chatbot_rest_client(app: web.Application) -> None:
    settings = get_plugin_settings(app)

    client = ChatbotRestClient(host=settings.CHATBOT_HOST, port=settings.CHATBOT_PORT)

    app[_APPKEY] = client


def get_chatbot_rest_client(app: web.Application) -> ChatbotRestClient:
    app_key: ChatbotRestClient = app[_APPKEY]
    return app_key
