from typing import Annotated, Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

_MIN_INPUT_MESSAGES: Final[int] = 1
_MAX_INPUT_MESSAGES: Final[int] = 20


class _UserMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    role: Literal["user"]
    content: str
    name: str = ""


class _AssistantMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role: Literal["assistant"]
    content: str


class _DeveloperMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role: Literal["developer"]
    content: str


type ChatCompletionRequestMessage = _UserMessage | _AssistantMessage | _DeveloperMessage


class ChatResponseFormat(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["text", "json_schema"]
    json_schema: dict[str, Any] | None = None


class ChatRequest(BaseModel):
    messages: Annotated[
        list[ChatCompletionRequestMessage],
        Field(
            min_length=_MIN_INPUT_MESSAGES, max_length=_MAX_INPUT_MESSAGES, description="List of messages in the chat"
        ),
    ]
    model: str
    metadata: dict[str, Any] = {}
    response_format: ChatResponseFormat | None = None
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
