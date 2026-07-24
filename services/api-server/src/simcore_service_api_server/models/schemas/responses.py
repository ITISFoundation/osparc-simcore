"""Pydantic models for OpenAI-compatible Responses API.

Minimal subset of the OpenAI Responses API schema. Fields can be added
as needed — the breaking-change check ensures we stay compatible.
"""

from enum import StrEnum
from typing import Annotated, Any, Final, Literal, get_args

import jsonschema
from pydantic import Discriminator, Field, Tag, TypeAdapter, field_validator
from pydantic_core import PydanticCustomError
from referencing.jsonschema import ObjectSchema

from ..domain.chatbot import ChatCompletionRequestMessage, ChatResponseFormat
from .base import ApiServerInputSchema, ApiServerOutputSchema

Temperature = Annotated[float, Field(ge=0, le=2)]

type MetadataKey = Annotated[str, Field(max_length=64)]
type MetadataValue = Annotated[str, Field(max_length=512)]

_ChatCompletionRequestMessageAdapter: Final[TypeAdapter[ChatCompletionRequestMessage]] = TypeAdapter(
    ChatCompletionRequestMessage
)


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


class ResponseFormatTextType(StrEnum):
    TEXT = "text"


class ResponseFormatJsonSchemaType(StrEnum):
    JSON_SCHEMA = "json_schema"


class ResponseFormatText(ApiServerInputSchema):
    type: ResponseFormatTextType


class TextResponseFormatJsonSchema(ApiServerInputSchema):
    type: ResponseFormatJsonSchemaType
    name: Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")]
    schema_: Annotated[ObjectSchema, Field(alias="schema")]
    description: str = ""
    strict: bool | None = None

    @field_validator("schema_")
    @classmethod
    def _validate_json_schema(cls, v: ObjectSchema) -> ObjectSchema:
        try:
            jsonschema.Draft7Validator.check_schema(v)
        except jsonschema.SchemaError as err:
            _error_type = "invalid_json_schema"
            _msg_template = "Invalid JSON Schema: {message}"
            raise PydanticCustomError(
                _error_type,
                _msg_template,
                {"message": err.message},
            ) from err
        return v

    def to_domain(self) -> "ChatResponseFormat":
        json_schema: dict = {
            "name": self.name,
            "schema": dict(self.schema_),
        }
        if self.description:
            json_schema["description"] = self.description
        if self.strict is not None:
            json_schema["strict"] = self.strict
        return ChatResponseFormat(type="json_schema", json_schema=json_schema)


type TextFormatParam = ResponseFormatText | TextResponseFormatJsonSchema


def _text_format_discriminator(v: TextFormatParam | dict) -> str:
    if isinstance(v, dict):
        discriminator = v.get("type", "text")
        return discriminator if isinstance(discriminator, str) else "text"
    return v.type


class TextParam(ApiServerInputSchema):
    format: Annotated[
        Annotated[ResponseFormatText, Tag("text")] | Annotated[TextResponseFormatJsonSchema, Tag("json_schema")],
        Discriminator(_text_format_discriminator),
    ] = ResponseFormatText(type=ResponseFormatTextType.TEXT)


class InputMessage(ApiServerInputSchema):
    role: Literal["user", "assistant", "developer"]
    content: Annotated[str, Field(min_length=1, max_length=100_000)]
    name: Annotated[str, Field(max_length=200)] = ""

    def to_domain_model(self) -> ChatCompletionRequestMessage:
        return _ChatCompletionRequestMessageAdapter.validate_python(self.model_dump())


class CreateResponseRequest(ApiServerInputSchema):
    """Request body for POST /responses."""

    background: Literal[True]
    input: Annotated[list[InputMessage], Field(min_length=1, max_length=50)]
    metadata: Annotated[dict[MetadataKey, MetadataValue], Field(max_length=16)] | None = None
    model: Any  # validation is done in validator because of OpenAI's tricky OAS
    temperature: Temperature
    text: TextParam = TextParam()

    @field_validator("model")
    @classmethod
    def _check_supported_model(cls, v: Any) -> str:
        supported = get_args(ChatModel)
        if not isinstance(v, str) or v not in supported:
            msg = f"Model '{v}' is not supported. Supported models: {sorted(supported)}"
            raise ValueError(msg)
        return v


class OutputTextContent(ApiServerOutputSchema):
    type: Literal["output_text"] = "output_text"
    text: str


class OutputMessage(ApiServerOutputSchema):
    type: Literal["message"] = "message"
    id: str
    status: Literal["in_progress", "completed", "incomplete"]
    role: Literal["assistant"] = "assistant"
    content: list[OutputTextContent]


class ResponseObject(ApiServerOutputSchema):
    """Response object returned by both POST and GET endpoints."""

    id: str
    object: ResponseObjectType = ResponseObjectType.RESPONSE
    background: bool | None = None
    error: dict[str, str] | None = None
    model: str | None = None
    output: list[OutputMessage] | None = None
    status: ResponseStatus = ResponseStatus.IN_PROGRESS
