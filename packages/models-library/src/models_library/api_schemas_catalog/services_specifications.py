from typing import Annotated

from pydantic import BaseModel, Field

from ..generated_models.docker_rest_api import ServiceSpec as DockerServiceSpec


class ServiceSpecifications(BaseModel):
    sidecar: Annotated[
        DockerServiceSpec | None,
        Field(
            description="schedule-time specifications for the service sidecar (follows Docker Service creation API, see https://docs.docker.com/engine/api/v1.25/#operation/ServiceCreate)",
        ),
    ] = None
    service: Annotated[
        DockerServiceSpec | None,
        Field(
            description="schedule-time specifications specifications for the service (follows Docker Service creation API (specifically only the Resources part), see https://docs.docker.com/engine/api/v1.41/#tag/Service/operation/ServiceCreate",
        ),
    ] = None


class ServiceSpecificationsGet(ServiceSpecifications): ...
