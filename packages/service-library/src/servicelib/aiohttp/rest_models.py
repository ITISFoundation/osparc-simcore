from dataclasses import dataclass, field
from typing import Any, ClassVar

from pydantic import BaseModel, Field


@dataclass
class LogMessage:
    message: str
    level: str = "INFO"
    logger: str = "user"


@dataclass
class ErrorDetail:
    code: str
    message: str
    resource: str | None
    field: str | None

    @classmethod
    def from_exception(cls, err: BaseException):
        return cls(
            code=err.__class__.__name__, message=str(err), resource=None, field=None
        )


@dataclass
class ResponseErrorBody:
    message: str
    status: int
    # Optional
    logs: list[LogMessage] = field(default_factory=list)
    errors: list[ErrorDetail] = field(default_factory=list)


#
# New
#


class OneError(BaseModel):
    msg: str
    type_: str | None = Field(None, alias="type")
    loc: str | None = None
    ctx: dict | None = None

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                # HTTP_422_UNPROCESSABLE_ENTITY
                {
                    "loc": "path.project_uuid",
                    "msg": "value is not a valid uuid",
                    "type": "type_error.uuid",
                },
                # HTTP_401_UNAUTHORIZED
                {
                    "msg": "You have to activate your account via email, before you can login",
                    "type": "activation_required",
                    "ctx": {"resend_email_url": "https://foo.io/resend?code=123456"},
                },
            ]
        }


class ManyErrors(BaseModel):
    msg: str
    details: list[OneError] = []

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                # Collects all errors in a body HTTP_422_UNPROCESSABLE_ENTITY
                "msg": "Invalid field/s 'body.x, body.z' in request",
                "details": [
                    {
                        "loc": "body.x",
                        "msg": "field required",
                        "type": "value_error.missing",
                    },
                    {
                        "loc": "body.z",
                        "msg": "field required",
                        "type": "value_error.missing",
                    },
                ],
            }
        }
