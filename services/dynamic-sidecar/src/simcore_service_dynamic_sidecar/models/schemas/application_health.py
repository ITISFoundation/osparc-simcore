from pydantic import BaseModel, Field


class ApplicationHealth(BaseModel):
    is_healthy: bool = Field(
        True, description="returns True if the service sis running correctly"
    )
