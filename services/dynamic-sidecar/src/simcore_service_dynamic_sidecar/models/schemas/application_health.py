from typing import Optional

from pydantic import BaseModel, Field


class ApplicationHealth(BaseModel):
    is_healthy: bool = Field(
        True, description="returns True if the service sis running correctly"
    )
    error_message: Optional[str] = Field(
        None, description="in case of error this gets set"
    )
