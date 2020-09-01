from typing import List, Optional

from pydantic import BaseModel, Field


class Error(BaseModel):
    code: Optional[str] = Field(None, description="Server Exception")


class ErrorType(BaseModel):
    message: str = Field(..., description="Error message")
    errors: Optional[List[Error]] = None
    status: int = Field(..., description="Error code")


class ErrorEnveloped(BaseModel):
    error: ErrorType
