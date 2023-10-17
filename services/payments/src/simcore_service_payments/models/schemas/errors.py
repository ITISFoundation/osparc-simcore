import http
from typing import Any

import httpx
from models_library.utils.pydantic_tools_extension import NOT_REQUIRED
from pydantic import BaseModel, Field


class DefaultApiError(BaseModel):
    name: str = Field(
        ...,
        description="Error identifier as a code or a name. Mostly for machine-machine communication.",
    )
    detail: Any | None = Field(NOT_REQUIRED, description="Human readable error message")

    @classmethod
    def from_status_code(
        cls, code: int, *, detail: str | None = None
    ) -> "DefaultApiError":
        assert httpx.codes.is_error(code)  # nosec
        httplib_code = http.HTTPStatus(code)

        return cls(
            name=httplib_code.phrase,
            detail=detail
            or httplib_code.description
            or httpx.codes.get_reason_phrase(code),
        )
