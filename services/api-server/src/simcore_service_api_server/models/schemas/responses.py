"""Pydantic models for OpenAI-compatible Responses API.

Minimal subset of the OpenAI Responses API schema. Fields can be added
as needed — the breaking-change check ensures we stay compatible.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class InputMessage(BaseModel):
    role: Literal["user", "assistant", "system", "developer"]
    content: str | list[dict[str, Any]]


class CreateResponseRequest(BaseModel):
    """Request body for POST /responses."""

    model: Any = None
    input: Any = None
    instructions: str | None = None
    temperature: float | None = None
    store: bool | None = None
    metadata: dict[str, str] | None = None
    previous_response_id: str | None = None


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
    created_at: float | None = None
    status: Literal["completed", "failed", "in_progress", "incomplete", "queued"] | None = None
    error: dict[str, Any] | None = None
    incomplete_details: dict[str, Any] | None = None
    instructions: str | list[Any] | None = None
    metadata: dict[str, str] | None = None
    model: str | None = None
    output: list[OutputMessage] | None = None
    temperature: float | None = None
    text: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, Any] = Field(default_factory=dict)
