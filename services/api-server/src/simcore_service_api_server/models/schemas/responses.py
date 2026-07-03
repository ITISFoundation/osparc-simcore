"""Pydantic models for OpenAI-compatible Responses API.

Minimal subset of the OpenAI Responses API schema. Fields can be added
as needed — the breaking-change check ensures we stay compatible.
"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, field_validator

Temperature = Annotated[float, Field(ge=0, le=2)]

ChatModel = Literal["gpt-3.5-turbo", "gpt-4.1-nano", "gpt-4o-mini", "gpt-5.2"]


class InputMessage(BaseModel):
    role: Literal["user", "assistant", "system", "developer"]
    content: str | list[dict[str, Any]]


class CreateResponseRequest(BaseModel):
    """Request body for POST /responses."""

    background: Literal[True]
    input: list[InputMessage]
    metadata: dict[str, str] | None = None
    model: Any
    temperature: Temperature

    @field_validator("model")
    @classmethod
    def _check_supported_model(cls, v: Any) -> str:
        if not isinstance(v, str) or v not in set(ChatModel.__args__):
            msg = f"Model '{v}' is not supported. Supported models: {sorted(ChatModel.__args__)}"
            raise ValueError(msg)
        return v


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


class ResponseObject(BaseModel):
    """Response object returned by both POST and GET endpoints."""

    id: str | None = None
    object: Literal["response"] = "response"
    background: bool | None = None
    created_at: float | None = None
    error: dict[str, Any] | None = None
    incomplete_details: dict[str, Any] | None = None
    instructions: str | list[Any] | None = None
    metadata: dict[str, str] | None = None
    model: str | None = None
    output: list[OutputMessage] | None = None
    status: Literal["completed", "failed", "in_progress", "incomplete", "queued"] | None = None
    temperature: Temperature | None = None
    text: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, Any] = Field(default_factory=dict)
