import http
from typing import Any

from pydantic import BaseModel, Field

from ..basic_types import IDStr


class DefaultApiError(BaseModel):
    name: IDStr = Field(
        ...,
        description="Error identifier as a code or a name. "
        "Mainly for machine-machine communication purposes.",
    )
    detail: Any | None = Field(default=None, description="Human readable error message")

    @classmethod
    def from_status_code(
        cls, code: int, *, detail: str | None = None
    ) -> "DefaultApiError":
        httplib_code = http.HTTPStatus(code)

        return cls(
            name=f"{code}",  # type: ignore[arg-type]
            detail=detail or httplib_code.description or httplib_code.phrase,
        )
