from typing import Optional

from pydantic import Field, validator

from .generated_models.docker_rest_api import ContainerSpec, ServiceSpec, TaskSpec


def to_snake_case(string: str) -> str:
    return "".join(["_" + i.lower() if i.isupper() else i for i in string]).lstrip("_")


class AioDockerContainerSpec(ContainerSpec):
    Env: Optional[dict[str, str]] = Field(
        None,
        description="aiodocker expects here a dictionary and re-convert it back internally`.\n",
    )

    @validator("Env", pre=True)
    @classmethod
    def convert_list_to_dict(cls, v):
        if v is not None and isinstance(v, list):
            converted_dict = {}
            for env in v:
                splitted_env = str(env).split("=", maxsplit=1)
                converted_dict[splitted_env[0]] = (
                    splitted_env[1] if len(splitted_env) > 1 else None
                )
            return converted_dict
        return v


class AioDockerTaskSpec(TaskSpec):
    ContainerSpec: Optional[AioDockerContainerSpec] = Field(
        None,
    )


class AioDockerServiceSpec(ServiceSpec):

    TaskTemplate: Optional[AioDockerTaskSpec] = None

    class Config(ServiceSpec.Config):
        alias_generator = to_snake_case
        allow_population_by_field_name = True
