""" Common models used in response payloads

- Enveloped response body
- Error model in Enveloped
- Flash message

NOTE: these are all Output models
"""

from typing import Any, ClassVar, TypeAlias

from pydantic import BaseModel, ValidationError


class OneError(BaseModel):
    msg: str
    # optional
    kind: str | None = None
    loc: str | None = None
    ctx: dict[str, Any] | None = None

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                # HTTP_422_UNPROCESSABLE_ENTITY
                {
                    "loc": "path.project_uuid",
                    "msg": "value is not a valid uuid",
                    "kind": "type_error.uuid",
                },
                # HTTP_401_UNAUTHORIZED
                {
                    "msg": "You have to activate your account via email, before you can login",
                    "kind": "activation_required",
                    "ctx": {"resend_email_url": "https://foo.io/resend?code=123456"},
                },
            ]
        }

    @classmethod
    def from_exception(cls, exc: Exception) -> "OneError":
        return cls(
            msg=f"{exc}",  # str(exc) always exists
            kind=exc.__class__.__name__,  # exception class name always exists
        )


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
                        "kind": "value_error.missing",
                    },
                    {
                        "loc": "body.z",
                        "msg": "field required",
                        "kind": "value_error.missing",
                    },
                ],
            }
        }


OneOrManyErrors: TypeAlias = OneError | ManyErrors


def loc_to_jq_filter(parts: tuple[int | str, ...]) -> str:
    """Converts Loc into jq filter

    SEE https://jqlang.github.io/jq/manual/#basic-filters
    """
    return "".join(["." + _ if isinstance(_, str) else f"[{_}]" for _ in parts])


def create_error_model_from_validation_error(
    validation_error: ValidationError, msg: str
) -> OneOrManyErrors:
    details = [
        OneError(
            msg=e["msg"],
            kind=e["type"],
            loc=loc_to_jq_filter(e["loc"]),
            ctx=e.get("ctx", None),
        )
        for e in validation_error.errors()
    ]

    assert details  # nosec

    if len(details) == 1:
        return details[0]
    return ManyErrors(msg=msg, details=details)


class FlashMessage(BaseModel):
    message: str
    level: str = "INFO"
    logger: str = "user"
