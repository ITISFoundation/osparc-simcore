import http
from typing import Annotated, Any

from pydantic import BaseModel, Field

from ..basic_types import IDStr


class DefaultApiError(BaseModel):
    name: Annotated[IDStr, Field(description="Exception's class name")]
    detail: Annotated[Any | None, Field(description="Human readable error message")] = (
        None
    )

    @classmethod
    def from_status_code(
        cls, code: int, *, detail: str | None = None
    ) -> "DefaultApiError":
        httplib_code = http.HTTPStatus(code)

        return cls(
            name=f"{code}",  # type: ignore[arg-type]
            detail=detail or httplib_code.description or httplib_code.phrase,
        )
