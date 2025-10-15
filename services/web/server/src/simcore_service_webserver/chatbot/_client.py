"""Interface to communicate with Fogbugz API

- Simple client to create cases in Fogbugz
"""

import logging
from typing import Any, Final
from urllib.parse import urljoin

import httpx
from aiohttp import web
from pydantic import BaseModel, Field
from servicelib.aiohttp import status
from tenacity import (
    retry,
    retry_if_exception_type,
    retry_if_result,
    stop_after_attempt,
    wait_exponential,
)

from .settings import ChatbotSettings, get_plugin_settings

_logger = logging.getLogger(__name__)


_JSON_CONTENT_TYPE = "application/json"


class ChatResponse(BaseModel):
    answer: str = Field(description="Answer from the chatbot")


def _should_retry(response: httpx.Response | None) -> bool:
    if response is None:
        return True
    return (
        response.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR
        or response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    )


def _chatbot_retry():
    """Retry configuration for chatbot API calls"""
    return retry(
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


class ChatbotRestClient:
    def __init__(self, chatbot_settings: ChatbotSettings) -> None:
        self._client = httpx.AsyncClient()
        self._chatbot_settings = chatbot_settings

    async def get_settings(self) -> dict[str, Any]:
        """Fetches chatbot settings"""
        url = urljoin(f"{self._chatbot_settings.base_url}", "/v1/chat/settings")

        @_chatbot_retry()
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

    async def ask_question(self, question: str) -> ChatResponse:
        """Asks a question to the chatbot"""
        url = urljoin(f"{self._chatbot_settings.base_url}", "/v1/chat")

        @_chatbot_retry()
        async def _request() -> httpx.Response:
            return await self._client.post(
                url,
                json={
                    "question": question,
                    "llm": self._chatbot_settings.CHATBOT_LLM_MODEL,
                    "embedding_model": self._chatbot_settings.CHATBOT_EMBEDDING_MODEL,
                },
                headers={
                    "Content-Type": _JSON_CONTENT_TYPE,
                    "Accept": _JSON_CONTENT_TYPE,
                },
            )

        try:
            response = await _request()
            response.raise_for_status()
            response_data: dict[str, Any] = response.json()
            return ChatResponse(**response_data)
        except Exception:
            _logger.error(  # noqa: TRY400
                "Failed to ask question to chatbot at %s", url
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
    chatbot_settings = get_plugin_settings(app)

    client = ChatbotRestClient(
        chatbot_settings=chatbot_settings,
    )

    app[_APPKEY] = client


def get_chatbot_rest_client(app: web.Application) -> ChatbotRestClient:
    app_key: ChatbotRestClient = app[_APPKEY]
    return app_key
