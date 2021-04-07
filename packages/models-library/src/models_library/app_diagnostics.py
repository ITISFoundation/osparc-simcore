from typing import Any, Dict

from pydantic import BaseModel, Field


class AppStatusCheck(BaseModel):
    name: str = Field(..., description="Application name")
    version: str = Field(..., description="Application's version")
    services: Dict[str, Any] = Field(
        {}, description="Other backend services connected from this service"
    )
