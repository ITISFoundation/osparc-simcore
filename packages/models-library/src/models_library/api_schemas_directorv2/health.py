from pydantic import BaseModel, ConfigDict


class HealthCheckGet(BaseModel):
    timestamp: str
    model_config = ConfigDict()
