from .docker_rest_api import ServiceSpec


def to_snake_case(string: str) -> str:
    return "".join(["_" + i.lower() if i.isupper() else i for i in string]).lstrip("_")


class AioDockerServiceSpec(ServiceSpec):
    class Config(ServiceSpec.Config):
        alias_generator = to_snake_case
        allow_population_by_field_name = True
