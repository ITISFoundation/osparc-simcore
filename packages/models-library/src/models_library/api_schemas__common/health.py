from pydantic import BaseModel, ConfigDict


class HealthCheckGet(BaseModel):
    timestamp: str
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "simcore_service_directorv2.api.routes.health@2023-07-03T12:59:12.024551+00:00"
            }
        }
    )
