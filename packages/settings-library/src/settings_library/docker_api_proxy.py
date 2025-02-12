from functools import cached_property

from pydantic import Field, SecretStr

from .base import BaseCustomSettings
from .basic_types import PortInt


class DockerApiProxysettings(BaseCustomSettings):
    DOCKER_API_PROXY_HOST: str = Field(
        description="hostname of the docker-api-proxy service"
    )
    DOCKER_API_PROXY_PORT: PortInt = Field(
        8888, description="port of the docker-api-proxy service"
    )
    DOCKER_API_PROXY_SECURE: bool = False

    DOCKER_API_PROXY_USER: str | None = None
    DOCKER_API_PROXY_PASSWORD: SecretStr | None = None

    @cached_property
    def base_url(self) -> str:
        protocl = "https" if self.DOCKER_API_PROXY_SECURE else "http"
        return f"{protocl}://{self.DOCKER_API_PROXY_HOST}:{self.DOCKER_API_PROXY_PORT}"
