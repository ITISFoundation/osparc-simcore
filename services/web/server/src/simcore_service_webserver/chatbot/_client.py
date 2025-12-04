import logging
from operator import index
from typing import Annotated, Any, Final, Literal

import httpx
from aiohttp import web
from pydantic import BaseModel, Field
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON

from .exceptions import NoResponseFromChatbotError
from .settings import ChatbotSettings, get_plugin_settings

_logger = logging.getLogger(__name__)


class ResponseMessage(BaseModel):
    content: str


class ResponseItem(BaseModel):
    index: int  # 0-based index of the response
    message: ResponseMessage


class ChatResponse(BaseModel):
    choices: Annotated[list[ResponseItem], Field(description="Answer from the chatbot")]


class Message(BaseModel):
    role: Literal["user", "assistant", "developer"]
    content: Annotated[str, Field(description="Content of the message")]


class ChatbotRestClient:
    def __init__(self, chatbot_settings: ChatbotSettings) -> None:
        self._client = httpx.AsyncClient()
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

    async def send(self, messages: list[Message]) -> ResponseMessage:
        """Send a list of messages to the chatbot and returns the chatbot's response message."""
        url = httpx.URL(self._chatbot_settings.base_url).join("/v1/chat/completions")

        async def _request() -> httpx.Response:
            return await self._client.post(
                url,
                json={
                    "messages": [msg.model_dump(mode="json") for msg in messages],
                    "model": self._chatbot_settings.CHATBOT_MODEL,
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
            chat_response = ChatResponse.model_validate(response.json())
            if len(chat_response.choices) == 0:
                raise NoResponseFromChatbotError("No choices returned from chatbot")
            return chat_response.choices[0].message

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
