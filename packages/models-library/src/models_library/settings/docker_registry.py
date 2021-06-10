from typing import Optional

from pydantic import BaseSettings, Field, SecretStr


class RegistrySettings(BaseSettings):

    auth: bool = Field(..., description="do registry authentication")
    path: Optional[str] = Field(
        None,
        description="development mode only, in case a local registry is used",
        env="REGISTRY_PATH",
    )
    url: str = Field("", description="url to the docker registry")

    user: str = Field(..., description="username to access the docker registry")
    password: SecretStr = Field(
        ..., description="password to access the docker registry", env="REGISTRY_PW"
    )
    ssl: bool = Field(..., description="access to registry through ssl")

    @property
    def resolved_registry_url(self) -> str:
        return self.path or self.url

    class Config:
        env_prefix = "REGISTRY_"
