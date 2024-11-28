from dataclasses import dataclass
from typing import Annotated

from models_library.generics import Envelope
from pydantic import BaseModel, ConfigDict, Field

from .basic_types import IDStr, LogLevel


class Log(BaseModel):
    level: LogLevel | None = Field("INFO", description="log level")
    message: str = Field(
        ...,
        description="log message. If logger is USER, then it MUST be human readable",
    )
    logger: str | None = Field(
        None, description="name of the logger receiving this message"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Hi there, Mr user",
                "level": "INFO",
                "logger": "user-logger",
            }
        }
    )


class ErrorItem(BaseModel):
    code: str = Field(
        ...,
        description="Typically the name of the exception that produced it otherwise some known error code",
    )
    message: str = Field(..., description="Error message specific to this item")
    resource: str | None = Field(
        None, description="API resource affected by this error"
    )
    field: str | None = Field(None, description="Specific field within the resource")


@dataclass
class LogMessageType:
    # NOTE: deprecated!
    message: str
    level: str = "INFO"
    logger: str = "user"


@dataclass
class ErrorItemType:
    # NOTE: deprecated!
    code: str
    message: str
    resource: str | None
    field: str | None

    @classmethod
    def from_error(cls, err: BaseException):
        return cls(
            code=err.__class__.__name__, message=str(err), resource=None, field=None
        )


class ErrorGet(BaseModel):
    message: Annotated[
        str,
        Field(
            min_length=5,
            description="Message displayed to the user",
        ),
    ]
    support_id: Annotated[
        IDStr | None,
        Field(description="ID to track the incident during support", alias="supportId"),
    ] = None

    # NOTE: The fields blow are DEPRECATED. Still here to keep compatibilty with front-end until updated
    status: Annotated[int, Field(deprecated=True)] = 400
    errors: Annotated[
        list[ErrorItemType],
        Field(deprecated=True, default_factory=list, json_schema_extra={"default": []}),
    ]
    logs: Annotated[
        list[LogMessageType],
        Field(deprecated=True, default_factory=list, json_schema_extra={"default": []}),
    ]

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",  # Used to prune extra fields from internal data
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "message": "Sorry you do not have sufficient access rights for product"
                },
                {
                    "message": "Opps this error was unexpected. We are working on that!",
                    "supportId": "OEC:12346789",
                },
            ]
        },
    )


class EnvelopedError(Envelope[None]):
    error: ErrorGet

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"error": {"message": "display error message here"}},
                {
                    "error": {"message": "failure", "supportId": "OEC:123455"},
                    "data": None,
                },
            ]
        },
    )
