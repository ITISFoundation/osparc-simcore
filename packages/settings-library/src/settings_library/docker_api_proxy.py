from functools import cached_property
from typing import Annotated

from pydantic import Field, SecretStr

from .base import BaseCustomSettings
from .basic_types import PortInt


class DockerApiProxysettings(BaseCustomSettings):
    DOCKER_API_PROXY_HOST: Annotated[
        str, Field(description="hostname of the docker-api-proxy service")
    ]
    DOCKER_API_PROXY_PORT: Annotated[
        PortInt, Field(description="port of the docker-api-proxy service")
    ] = 8888
    DOCKER_API_PROXY_SECURE: bool = False

    DOCKER_API_PROXY_USER: str
    DOCKER_API_PROXY_PASSWORD: SecretStr

    @cached_property
    def base_url(self) -> str:
        protocl = "https" if self.DOCKER_API_PROXY_SECURE else "http"
        return f"{protocl}://{self.DOCKER_API_PROXY_HOST}:{self.DOCKER_API_PROXY_PORT}"
