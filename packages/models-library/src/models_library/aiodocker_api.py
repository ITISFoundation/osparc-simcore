from pydantic import ConfigDict, Field, field_validator

from .generated_models.docker_rest_api import (
    ContainerSpec,
    ResourceObject,
    Resources1,
    ServiceSpec,
    TaskSpec,
)
from .utils.change_case import camel_to_snake


class AioDockerContainerSpec(ContainerSpec):
    Env: dict[str, str | None] | None = Field(  # type: ignore
        default=None,
        description="aiodocker expects here a dictionary and re-convert it back internally`.\n",
    )

    @field_validator("Env", mode="before")
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
    Reservation: ResourceObject | None = Field(
        None, description="Define resources reservation.", alias="Reservations"
    )

    model_config = ConfigDict(populate_by_name=True)


class AioDockerTaskSpec(TaskSpec):
    ContainerSpec: AioDockerContainerSpec | None = Field(
        None,
    )

    Resources: AioDockerResources1 | None = Field(
        None,
        description="Resource requirements which apply to each individual container created\nas part of the service.\n",
    )


class AioDockerServiceSpec(ServiceSpec):
    TaskTemplate: AioDockerTaskSpec | None = None

    model_config = ConfigDict(alias_generator=camel_to_snake, populate_by_name=True)
