import logging
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI
from settings_library.tracing import TracingSettings

from ..models.domain.chatbot import (
    ChatCompletionRequestMessage,
    ChatRequest,
    CreateChatCompletionResponse,
)
from ..utils.client_base import BaseServiceClientApi, setup_client_instance

_logger = logging.getLogger(__name__)


# Client


@dataclass
class ChatbotApi(BaseServiceClientApi):
    """Client for the chatbot backend service."""

    async def create_chat_completion(
        self,
        *,
        messages: list[ChatCompletionRequestMessage],
        model: str,
        metadata: dict[str, Any],
        temperature: float = 1.0,
        top_p: float = 1.0,
    ) -> CreateChatCompletionResponse:
        request = ChatRequest(
            messages=messages,
            model=model,
            metadata=metadata,
            temperature=temperature,
            top_p=top_p,
        )
        response = await self.client.post(
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
