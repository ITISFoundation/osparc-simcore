import http
from typing import Any

from common_library.pydantic_basic_types import IDStr
from pydantic import BaseModel, Field

from ..utils.pydantic_tools_extension import NOT_REQUIRED


class DefaultApiError(BaseModel):
    name: IDStr = Field(
        ...,
        description="Error identifier as a code or a name. "
        "Mainly for machine-machine communication purposes.",
    )
    detail: Any | None = Field(NOT_REQUIRED, description="Human readable error message")

    @classmethod
    def from_status_code(
        cls, code: int, *, detail: str | None = None
    ) -> "DefaultApiError":
        httplib_code = http.HTTPStatus(code)

        return cls(
            name=f"{code}",  # type: ignore[arg-type]
            detail=detail or httplib_code.description or httplib_code.phrase,
        )
