from typing import Optional

from pydantic import Field, validator

from .generated_models.docker_rest_api import (
    ContainerSpec,
    ResourceObject,
    Resources1,
    ServiceSpec,
    TaskSpec,
)
from .utils.converters import to_snake_case


class AioDockerContainerSpec(ContainerSpec):
    Env: Optional[dict[str, Optional[str]]] = Field(
        None,
        description="aiodocker expects here a dictionary and re-convert it back internally`.\n",
    )

    @validator("Env", pre=True)
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
    Reservation: Optional[ResourceObject] = Field(
        None, description="Define resources reservation.", alias="Reservations"
    )

    class Config(Resources1.Config):
        allow_population_by_field_name = True


class AioDockerTaskSpec(TaskSpec):
    ContainerSpec: Optional[AioDockerContainerSpec] = Field(
        None,
    )

    Resources: Optional[AioDockerResources1] = Field(
        None,
        description="Resource requirements which apply to each individual container created\nas part of the service.\n",
    )


class AioDockerServiceSpec(ServiceSpec):

    TaskTemplate: Optional[AioDockerTaskSpec] = None

    class Config(ServiceSpec.Config):
        alias_generator = to_snake_case
        allow_population_by_field_name = True
