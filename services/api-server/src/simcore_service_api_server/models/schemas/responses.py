"""Pydantic models for OpenAI-compatible Responses API."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class InputMessage(BaseModel):
    role: Literal["user", "assistant", "system", "developer"]
    content: str | list[dict[str, Any]]


class ResponseTextConfig(BaseModel):
    format: dict[str, Any] | None = Field(default_factory=lambda: {"type": "text"})


class FunctionToolDefinition(BaseModel):
    type: Literal["function"] = "function"
    name: str
    description: str | None = None
    parameters: dict[str, Any] | None = None
    strict: bool | None = None


type ToolDefinition = FunctionToolDefinition | dict[str, Any]


class CreateResponseRequest(BaseModel):
    """Request body for POST /responses (OpenAI Responses API compatible)."""

    model: str
    input: str | list[InputMessage | dict[str, Any]]
    instructions: str | None = None
    max_output_tokens: int | None = None
    metadata: dict[str, str] | None = None
    parallel_tool_calls: bool | None = None
    previous_response_id: str | None = None
    store: bool | None = None
    stream: bool | None = None
    temperature: Annotated[float | None, Field(ge=0, le=2)] = None
    text: ResponseTextConfig | None = None
    tool_choice: str | dict[str, Any] | None = None
    tools: list[ToolDefinition] | None = None
    top_p: Annotated[float | None, Field(ge=0, le=1)] = None
    truncation: Literal["auto", "disabled"] | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "model": "gpt-4o",
                "input": "Tell me a three sentence bedtime story about a unicorn.",
            }
        }
    )


class OutputTextContent(BaseModel):
    type: Literal["output_text"] = "output_text"
    text: str
    annotations: list[dict[str, Any]] = Field(default_factory=list)


class OutputMessage(BaseModel):
    type: Literal["message"] = "message"
    id: str
    status: Literal["in_progress", "completed", "incomplete"]
    role: Literal["assistant"] = "assistant"
    content: list[OutputTextContent]


class ResponseError(BaseModel):
    code: str
    message: str


class IncompleteDetails(BaseModel):
    reason: str


class InputTokensDetails(BaseModel):
    cached_tokens: int = 0


class OutputTokensDetails(BaseModel):
    reasoning_tokens: int = 0


class ResponseUsage(BaseModel):
    input_tokens: int
    input_tokens_details: InputTokensDetails
    output_tokens: int
    output_tokens_details: OutputTokensDetails
    total_tokens: int


class ResponseObject(BaseModel):
    """Response object returned by both POST and GET endpoints."""

    id: str
    object: Literal["response"] = "response"
    created_at: int
    status: Literal["completed", "failed", "in_progress", "incomplete", "queued"]
    error: ResponseError | None = None
    incomplete_details: IncompleteDetails | None = None
    instructions: str | None = None
    max_output_tokens: int | None = None
    metadata: dict[str, str] | None = None
    model: str
    output: list[OutputMessage]
    parallel_tool_calls: bool = True
    previous_response_id: str | None = None
    temperature: float | None = 1.0
    text: ResponseTextConfig | None = None
    tool_choice: str | dict[str, Any] | None = "auto"
    tools: list[ToolDefinition] = Field(default_factory=list)
    top_p: float | None = 1.0
    truncation: Literal["auto", "disabled"] | None = "disabled"
    usage: ResponseUsage | None = None
    user: str | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "resp_67cb71b351908190a308f3859487620d06981a8637e6bc44",
                "object": "response",
                "created_at": 1741386163,
                "status": "completed",
                "error": None,
                "incomplete_details": None,
                "instructions": None,
                "max_output_tokens": None,
                "model": "gpt-4o-2024-08-06",
                "output": [
                    {
                        "type": "message",
                        "id": "msg_67cb71b3c2b0819084d481baaaf148f206981a8637e6bc44",
                        "status": "completed",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "Hello! How can I help you today?",
                                "annotations": [],
                            }
                        ],
                    }
                ],
                "parallel_tool_calls": True,
                "previous_response_id": None,
                "temperature": 1.0,
                "text": {"format": {"type": "text"}},
                "tool_choice": "auto",
                "tools": [],
                "top_p": 1.0,
                "truncation": "disabled",
                "usage": {
                    "input_tokens": 32,
                    "input_tokens_details": {"cached_tokens": 0},
                    "output_tokens": 18,
                    "output_tokens_details": {"reasoning_tokens": 0},
                    "total_tokens": 50,
                },
                "user": None,
                "metadata": {},
            }
        }
    )
