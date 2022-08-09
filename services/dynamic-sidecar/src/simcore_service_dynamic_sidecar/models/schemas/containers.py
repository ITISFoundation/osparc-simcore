from pydantic import BaseModel


class ContainersCreate(BaseModel):
    docker_compose_yaml: str
