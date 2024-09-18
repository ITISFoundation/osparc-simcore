from pydantic import BaseModel, Field

from ..generated_models.docker_rest_api import ServiceSpec as DockerServiceSpec


class ServiceSpecifications(BaseModel):
    sidecar: DockerServiceSpec | None = Field(
        default=None,
        description="schedule-time specifications for the service sidecar (follows Docker Service creation API, see https://docs.docker.com/engine/api/v1.25/#operation/ServiceCreate)",
    )
    service: DockerServiceSpec | None = Field(
        default=None,
        description="schedule-time specifications specifications for the service (follows Docker Service creation API (specifically only the Resources part), see https://docs.docker.com/engine/api/v1.41/#tag/Service/operation/ServiceCreate",
    )


class ServiceSpecificationsGet(ServiceSpecifications):
    ...
