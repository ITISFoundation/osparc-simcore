import logging
from typing import Annotated, Any, Final

import httpx
from aiohttp import web
from pydantic import BaseModel, Field
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON

from .settings import ChatbotSettings, get_plugin_settings

_logger = logging.getLogger(__name__)


class ChatResponse(BaseModel):
    answer: Annotated[str, Field(description="Answer from the chatbot")]


class ChatbotRestClient:
    def __init__(self, chatbot_settings: ChatbotSettings) -> None:
        self._client = httpx.AsyncClient()  # MD: todo
        self._chatbot_settings = chatbot_settings

    async def get_settings(self) -> dict[str, Any]:
        """Fetches chatbot settings"""
        url = httpx.URL(self._chatbot_settings.base_url).join("/v1/chat/settings")

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
        url = httpx.URL(self._chatbot_settings.base_url).join("/v1/chat")

        async def _request() -> httpx.Response:
            return await self._client.post(
                url,
                json={
                    "question": question,
                    "llm": self._chatbot_settings.CHATBOT_LLM_MODEL,
                    "embedding_model": self._chatbot_settings.CHATBOT_EMBEDDING_MODEL,
                },
                headers={
                    "Content-Type": MIMETYPE_APPLICATION_JSON,
                    "Accept": MIMETYPE_APPLICATION_JSON,
                },
                timeout=httpx.Timeout(60.0),
            )

        try:
            response = await _request()
            response.raise_for_status()
            return ChatResponse.model_validate(response.json())
        except Exception:
            _logger.error(  # noqa: TRY400
                "Failed to ask question to chatbot at %s", url
            )
            raise


_APPKEY: Final = web.AppKey(ChatbotRestClient.__name__, ChatbotRestClient)


async def setup_chatbot_rest_client(app: web.Application) -> None:
    chatbot_settings = get_plugin_settings(app)

    client = ChatbotRestClient(
        chatbot_settings=chatbot_settings,
    )

    app[_APPKEY] = client

    # Add cleanup on app shutdown
    async def cleanup_chatbot_client(app: web.Application) -> None:
        client = app.get(_APPKEY)
        if client:
            await client._client.aclose()  # pylint: disable=protected-access  # noqa: SLF001

    app.on_cleanup.append(cleanup_chatbot_client)


def get_chatbot_rest_client(app: web.Application) -> ChatbotRestClient:
    app_key: ChatbotRestClient = app[_APPKEY]
    return app_key
