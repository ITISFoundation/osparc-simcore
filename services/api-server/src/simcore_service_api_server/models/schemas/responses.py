"""Pydantic models for OpenAI-compatible Responses API.

Minimal subset of the OpenAI Responses API schema. Fields can be added
as needed — the breaking-change check ensures we stay compatible.
"""

from enum import StrEnum
from typing import Annotated, Any, Literal, get_args

from pydantic import BaseModel, Field, field_validator

Temperature = Annotated[float, Field(ge=0, le=2)]

type MetadataKey = Annotated[str, Field(max_length=64)]
type MetadataValue = Annotated[str, Field(max_length=512)]


class ResponseStatus(StrEnum):
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"
    IN_PROGRESS = "in_progress"
    INCOMPLETE = "incomplete"
    QUEUED = "queued"


class ResponseObjectType(StrEnum):
    RESPONSE = "response"


ChatModel = Literal["gpt-3.5-turbo", "gpt-4.1-nano", "gpt-4o-mini", "gpt-5.2"]


class InputMessage(BaseModel):
    role: Literal["user", "assistant", "system", "developer"]
    content: Annotated[str, Field(min_length=1, max_length=100_000)]


class CreateResponseRequest(BaseModel):
    """Request body for POST /responses."""

    background: Literal[True]
    input: Annotated[list[InputMessage], Field(min_length=1, max_length=50)]
    metadata: Annotated[dict[MetadataKey, MetadataValue], Field(max_length=16)] | None = None
    model: Any  # validation is done in validator because of OpenAI's tricky OAS
    temperature: Temperature

    @field_validator("model")
    @classmethod
    def _check_supported_model(cls, v: Any) -> str:
        supported = get_args(ChatModel)
        if not isinstance(v, str) or v not in supported:
            msg = f"Model '{v}' is not supported. Supported models: {sorted(supported)}"
            raise ValueError(msg)
        return v


class OutputTextContent(BaseModel):
    type: Literal["output_text"] = "output_text"
    text: str


class OutputMessage(BaseModel):
    type: Literal["message"] = "message"
    id: str
    status: Literal["in_progress", "completed", "incomplete"]
    role: Literal["assistant"] = "assistant"
    content: list[OutputTextContent]


class ResponseObject(BaseModel):
    """Response object returned by both POST and GET endpoints."""

    id: str
    object: ResponseObjectType = ResponseObjectType.RESPONSE
    background: bool | None = None
    error: dict[str, str] | None = None
    model: str | None = None
    output: list[OutputMessage] | None = None
    status: ResponseStatus = ResponseStatus.IN_PROGRESS
