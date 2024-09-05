from models_library.services_creation import CreateServiceMetricsAdditionalParams
from pydantic import BaseModel


class ContainersComposeSpec(BaseModel):
    docker_compose_yaml: str


class ContainersCreate(BaseModel):
    metrics_params: CreateServiceMetricsAdditionalParams
