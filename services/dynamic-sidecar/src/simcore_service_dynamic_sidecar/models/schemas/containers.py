from typing import TypeAlias

from models_library.services_creation import CreateServiceMetricsAdditionalParams
from pydantic import BaseModel

DcokerComposeYamlStr: TypeAlias = str


class ContainersComposeSpec(BaseModel):
    docker_compose_yaml: DcokerComposeYamlStr


class ContainersCreate(BaseModel):
    metrics_params: CreateServiceMetricsAdditionalParams
