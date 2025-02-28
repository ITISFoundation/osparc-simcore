from models_library.api_schemas_dynamic_sidecar.containers import DcokerComposeYamlStr
from models_library.services_creation import CreateServiceMetricsAdditionalParams
from pydantic import BaseModel


class ContainersComposeSpec(BaseModel):
    docker_compose_yaml: DcokerComposeYamlStr


class ContainersCreate(BaseModel):
    metrics_params: CreateServiceMetricsAdditionalParams
