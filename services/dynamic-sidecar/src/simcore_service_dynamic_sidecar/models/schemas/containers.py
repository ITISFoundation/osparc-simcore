from pydantic import BaseModel


class ContainersComposeSpec(BaseModel):
    docker_compose_yaml: str
