import logging
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI
from settings_library.tracing import TracingSettings

from ..core.settings import ChatbotSettings
from ..models.domain.chatbot import (
    ChatCompletionRequestMessage,
    ChatRequest,
    CreateChatCompletionResponse,
)
from ..models.schemas.responses import ChatModel
from ..utils.client_base import BaseServiceClientApi, setup_client_instance

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
        model: ChatModel,
        metadata: dict[str, Any],
        temperature: float = 1.0,
        top_p: float = 1.0,
    ) -> CreateChatCompletionResponse:
        # ensure the graph specified in settings are used
        _metadata = deepcopy(metadata)
        _metadata["graph_name"] = self._chatbot_settings.GRAPH_NAME

        request = ChatRequest(
            messages=messages,
            model=model,
            metadata=_metadata,
            temperature=temperature,
            top_p=top_p,
        )
        response = await self._api.client.post(
            "/v1/chat/completions",
            json=request.model_dump(),
        )
        response.raise_for_status()
        return CreateChatCompletionResponse.model_validate(response.json())


# APP SETUP -------------------------------------------------------------------


def setup(
    app: FastAPI,
    *,
    base_url: str,
    tracing_settings: TracingSettings | None,
) -> None:
    setup_client_instance(
        app,
        ChatbotApi,
        api_baseurl=base_url,
        service_name="chatbot",
        tracing_settings=tracing_settings,
        health_check_path="/v1/health",
    )
