from pydantic import BaseModel, Field


class Error(BaseModel):
    code: str | None = Field(None, description="Server Exception")


class ErrorType(BaseModel):
    message: str = Field(..., description="Error message")
    errors: list[Error] | None = None
    status: int = Field(..., description="Error code")


class ErrorEnveloped(BaseModel):
    error: ErrorType
