from typing import Optional

from pydantic import Field, SecretStr

from .base import BaseCustomSettings


class RegistrySettings(BaseCustomSettings):

    REGISTRY_AUTH: bool = Field(..., description="do registry authentication")
    REGISTRY_PATH: Optional[str] = Field(
        None, description="development mode only, in case a local registry is used"
    )
    REGISTRY_URL: str = Field("", description="url to the docker registry")

    REGISTRY_USER: str = Field(
        ..., description="username to access the docker registry"
    )
    REGISTRY_PW: SecretStr = Field(
        ..., description="password to access the docker registry"
    )
    REGISTRY_SSL: bool = Field(..., description="access to registry through ssl")

    @property
    def resolved_registry_url(self) -> str:
        return self.REGISTRY_PATH or self.REGISTRY_URL
