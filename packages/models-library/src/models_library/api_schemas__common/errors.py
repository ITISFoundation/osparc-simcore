import http
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..basic_types import IDStr
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
            name=IDStr(f"{code}"),
            detail=detail or httplib_code.description or httplib_code.phrase,
        )

    model_config = ConfigDict(arbitrary_types_allowed=True)
