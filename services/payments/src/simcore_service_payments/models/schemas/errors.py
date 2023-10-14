from typing import Any

from models_library.utils.pydantic_tools_extension import NOT_REQUIRED
from pydantic import BaseModel, Field


class DefaultApiError(BaseModel):
    name: str = Field(None, description="Error identifier as a code or a name")
    message: str | None = Field(
        NOT_REQUIRED, description="Human readable error message"
    )
    detail: Any | None = Field(NOT_REQUIRED, description="Further details")
