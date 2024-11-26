from pydantic import Field, field_validator

from .generated_models.docker_rest_api import (
    ContainerSpec,
    ResourceObject,
    Resources1,
    ServiceSpec,
    TaskSpec,
)


class AioDockerContainerSpec(ContainerSpec):
    env: dict[str, str | None] | None = Field(  # type: ignore[assignment]
        default=None,
        alias="Env",
        description="aiodocker expects here a dictionary and re-convert it back internally",
    )

    @field_validator("env", mode="before")
    @classmethod
    def convert_list_to_dict(cls, v):
        if v is not None and isinstance(v, list):
            converted_dict = {}
            for env in v:
                splitted_env = f"{env}".split("=", maxsplit=1)
                converted_dict[splitted_env[0]] = (
                    splitted_env[1] if len(splitted_env) > 1 else None
                )
            return converted_dict
        return v


class AioDockerResources1(Resources1):
    # NOTE: The Docker REST API documentation is wrong!!!
    # Do not set that back to singular Reservation.
    reservation: ResourceObject | None = Field(
        None, description="Define resources reservation.", alias="Reservations"
    )


class AioDockerTaskSpec(TaskSpec):
    container_spec: AioDockerContainerSpec | None = Field(
        default=None, alias="ContainerSpec"
    )

    resources: AioDockerResources1 | None = Field(default=None, alias="Resources")


class AioDockerServiceSpec(ServiceSpec):
    task_template: AioDockerTaskSpec | None = Field(default=None, alias="TaskTemplate")
