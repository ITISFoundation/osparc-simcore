from typing import Optional

from models_library.generated_models.docker_rest_api import (
    ServiceSpec as DockerServiceSpec,
)
from pydantic import BaseModel, Field


class ServiceSpecifications(BaseModel):
    sidecar: Optional[DockerServiceSpec] = Field(
        default=None,
        description="schedule-time specifications for the service sidecar (follows Docker Service creation API, see https://docs.docker.com/engine/api/v1.25/#operation/ServiceCreate)",
    )


class ServiceSpecificationsGet(ServiceSpecifications):
    ...
