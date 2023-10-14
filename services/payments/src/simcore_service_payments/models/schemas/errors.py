import http
from typing import Any

import httpx
from models_library.utils.pydantic_tools_extension import NOT_REQUIRED
from pydantic import BaseModel, Field


class DefaultApiError(BaseModel):
    name: str = Field(None, description="Error identifier as a code or a name")
    message: str | None = Field(
        NOT_REQUIRED, description="Human readable error message"
    )
    detail: Any | None = Field(NOT_REQUIRED, description="Further details")

    @classmethod
    def from_status_code(
        cls, code: int, *, is_human_readable: bool = True
    ) -> "DefaultApiError":
        assert httpx.codes.is_error(code)  # nosec
        httplib_code = http.HTTPStatus(code)

        message = None
        detail = None
        if is_human_readable:
            message = httplib_code.description or httplib_code.phrase
            detail = httpx.codes.get_reason_phrase(code)

        return DefaultApiError(
            name=httplib_code.phrase,
            message=message,
            detail=detail,
        )
