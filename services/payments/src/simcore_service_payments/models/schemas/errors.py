from typing import Any

from models_library.utils.pydantic_tools_extension import NOT_REQUIRED
from pydantic import BaseModel, Field


class Error(BaseModel):
    error: str = Field(..., description="Standarized error name")
    message: str = Field(..., description="Human readable error message")
    details: Any = Field(NOT_REQUIRED, description="Further details")
