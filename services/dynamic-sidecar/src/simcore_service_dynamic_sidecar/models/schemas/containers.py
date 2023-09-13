from models_library.services_creation import CreateServiceMetricsAdditionalParams
from pydantic import BaseModel


class ContainersCreate(BaseModel):
    docker_compose_yaml: str
    metrics_params: CreateServiceMetricsAdditionalParams
