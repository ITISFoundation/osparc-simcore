from typing import Annotated

from pydantic import BaseModel, Field


class Error(BaseModel):
    code: Annotated[str | None, Field(description="Server Exception")] = None


class ErrorType(BaseModel):
    message: Annotated[str, Field(description="Error message")]
    status: Annotated[int, Field(description="Error code")]
    errors: list[Error] | None = None


class ErrorEnveloped(BaseModel):
    error: ErrorType
