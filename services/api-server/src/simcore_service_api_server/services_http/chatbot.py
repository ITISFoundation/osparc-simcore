import logging
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from settings_library.tracing import TracingSettings

from ..core.settings import ChatbotSettings
from ..models.domain.chatbot import (
    ChatCompletionRequestMessage,
    ChatRequest,
    ChatResponseFormat,
    CreateChatCompletionResponse,
)
from ..utils.client_base import BaseServiceClientApi, configure_client_instance

_logger = logging.getLogger(__name__)


# Client


class ChatbotApi(BaseServiceClientApi): ...


@dataclass(frozen=True)
class ChatbotSession:
    """Client for the chatbot backend service."""

    _chatbot_settings: ChatbotSettings
    _api: ChatbotApi

    async def create_chat_completion(
        self,
        *,
        messages: list[ChatCompletionRequestMessage],
        model: str,
        metadata: dict[str, Any],
        temperature: float = 1.0,
        top_p: float = 1.0,
        response_format: ChatResponseFormat | None = None,
    ) -> CreateChatCompletionResponse:
        # ensure the graph specified in settings are used
        _metadata = deepcopy(metadata)
        _metadata["graph_name"] = self._chatbot_settings.GRAPH_NAME

        request = ChatRequest(
            messages=messages,
            model=model,
            metadata=_metadata,
            response_format=response_format,
            temperature=temperature,
            top_p=top_p,
        )
        response = await self._api.client.post(
            "/v1/chat/completions",
            json=request.model_dump(exclude_none=True),
            timeout=self._chatbot_settings.CHATBOT_REQUEST_TIMEOUT_SECONDS.seconds,
        )
        response.raise_for_status()
        return CreateChatCompletionResponse.model_validate(response.json())

    async def stream_chat_completion(
        self,
        *,
        messages: list[ChatCompletionRequestMessage],
        model: str,
        metadata: dict[str, Any],
        temperature: float = 1.0,
        top_p: float = 1.0,
        response_format: ChatResponseFormat | None = None,
    ) -> httpx.Response:
        """Opens a streamed chat completion. Headers/status are already available on return,
        but the body is not yet consumed: the caller must iterate `response.aiter_bytes()`
        and call `response.aclose()` once done (e.g. via an `SseStreamingResponse`)."""
        _metadata = deepcopy(metadata)
        _metadata["graph_name"] = self._chatbot_settings.GRAPH_NAME

        request = ChatRequest(
            messages=messages,
            model=model,
            metadata=_metadata,
            response_format=response_format,
            temperature=temperature,
            top_p=top_p,
            stream=True,
        )
        http_request = self._api.client.build_request(
            "POST",
            "/v1/chat/completions",
            json=request.model_dump(exclude_none=True),
            timeout=self._chatbot_settings.CHATBOT_REQUEST_TIMEOUT_SECONDS.seconds,
        )
        response = await self._api.client.send(http_request, stream=True)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError:
            # read the body before closing so callers can inspect/relay the downstream error detail
            await response.aread()
            await response.aclose()
            raise
        return response


# APP SETUP -------------------------------------------------------------------


def configure(
    app: FastAPI,
    app_lifespan: LifespanManager[FastAPI],
    *,
    base_url: str,
    tracing_settings: TracingSettings | None,
) -> None:
    configure_client_instance(
        app,
        app_lifespan,
        ChatbotApi,
        api_baseurl=base_url,
        service_name="chatbot",
        tracing_settings=tracing_settings,
        health_check_path="/v1/health",
    )
