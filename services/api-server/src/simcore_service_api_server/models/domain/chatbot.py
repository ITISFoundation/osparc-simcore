from enum import StrEnum
from typing import Annotated, Any, Final

from pydantic import BaseModel, Field

_MIN_INPUT_MESSAGES: Final[int] = 1
_MAX_INPUT_MESSAGES: Final[int] = 20


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
        Field(
            min_length=_MIN_INPUT_MESSAGES, max_length=_MAX_INPUT_MESSAGES, description="List of messages in the chat"
        ),
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
