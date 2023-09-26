from typing import Any, ClassVar

from pydantic import BaseModel


class HealthCheckGet(BaseModel):
    timestamp: str

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "timestamp": "simcore_service_directorv2.api.routes.health@2023-07-03T12:59:12.024551+00:00"
            }
        }
