from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, Field


class RoleEnum(StrEnum):
    ASSISTANT = "assistant"
    DEVELOPER = "developer"
    USER = "user"


class ChatCompletionRequestMessage(BaseModel):
    role: RoleEnum
    content: str | None
    name: str = ""


class ChatRequest(BaseModel):
    messages: Annotated[
        list[ChatCompletionRequestMessage],
        Field(min_length=1, max_length=20, description="List of messages in the chat"),
    ]
    model: str
    metadata: dict[str, Any] = {}
    temperature: Annotated[float, Field(ge=0, le=1.9)] = 1.0
    top_p: Annotated[float, Field(ge=0, le=1.0)] = 1.0


class ChatCompletionResponseMessage(BaseModel):
    content: str | None


class ChatCompletionsChoice(BaseModel):
    index: int
    message: ChatCompletionResponseMessage


class CreateChatCompletionResponse(BaseModel):
    model_config = {"extra": "ignore"}

    id: str
    choices: list[ChatCompletionsChoice]
    metadata: dict[str, str | int] | None = None
