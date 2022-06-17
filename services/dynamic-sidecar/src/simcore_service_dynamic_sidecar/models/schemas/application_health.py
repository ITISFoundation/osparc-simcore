from typing import Optional

from pydantic import BaseModel, Field


class ApplicationHealth(BaseModel):
    is_healthy: bool = Field(
        default=True, description="returns True if the service sis running correctly"
    )
    error_message: Optional[str] = Field(
        default=None, description="in case of error this gets set"
    )
