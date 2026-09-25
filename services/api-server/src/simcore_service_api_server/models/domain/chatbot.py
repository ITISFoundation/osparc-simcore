from typing import Annotated, Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

Temperature = Annotated[float, Field(ge=0, le=2)]
TopP = Annotated[float, Field(ge=0, le=1)]

DEFAULT_TEMPERATURE: Final[Temperature] = 1.0
# NOTE the api-server does not expose top_p to callers yet, so this is the fixed value relayed downstream
DEFAULT_TOP_P: Final[TopP] = 1.0


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
    type: Literal["text", "json_schema"]
    json_schema: dict[str, Any] | None = None


class ChatRequest(BaseModel):
    # NOTE None is used as a sentinel for optional fields, not as an actual value (it will never be sent)
    messages: list[ChatCompletionRequestMessage]
    model: str
    metadata: dict[str, Any] = {}
    response_format: ChatResponseFormat | None = None
    stream: bool = False
    temperature: Temperature = DEFAULT_TEMPERATURE
    top_p: TopP = DEFAULT_TOP_P


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
