from typing import Optional

from pydantic import BaseSettings, Field, SecretStr


class RegistrySettings(BaseSettings):
    registry_auth: bool = Field(..., description="do registry authentication")
    registry_path: Optional[str] = Field(
        None,
        description="development mode only, in case a local registry is used",
        env="REGISTRY_PATH",
    )
    registry_url: str = Field("", description="url to the docker registry")

    registry_user: str = Field(
        ..., description="username to access the docker registry"
    )
    registry_password: SecretStr = Field(
        ..., description="password to access the docker registry"
    )
    registry_ssl: bool = Field(..., description="access to registry through ssl")

    @property
    def resolved_registry_url(self) -> str:
        return self.registry_path or self.registry_url

    class Config:
        env_prefix = "REGISTRY_"
