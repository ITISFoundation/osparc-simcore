from functools import cached_property
from typing import Any

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import SettingsConfigDict

from .base import BaseCustomSettings


class RegistrySettings(BaseCustomSettings):
    REGISTRY_AUTH: bool = Field(..., description="do registry authentication")
    REGISTRY_PATH: str | None = Field(
        default=None,
        description="development mode only, in case a local registry is used",
    )
    # NOTE: name is missleading, http or https protocol are not included
    REGISTRY_URL: str = Field(default="", description="address to the docker registry")

    REGISTRY_USER: str = Field(
        ..., description="username to access the docker registry"
    )
    REGISTRY_PW: SecretStr = Field(
        ..., description="password to access the docker registry"
    )
    REGISTRY_SSL: bool = Field(..., description="access to registry through ssl")

    @field_validator("REGISTRY_PATH", mode="before")
    @classmethod
    def _escape_none_string(cls, v) -> Any | None:
        return None if v == "None" else v

    @cached_property
    def resolved_registry_url(self) -> str:
        return self.REGISTRY_PATH or self.REGISTRY_URL

    @cached_property
    def api_url(self) -> str:
        return f"{self.REGISTRY_URL}/v2"

    model_config = SettingsConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "REGISTRY_AUTH": "True",
                    "REGISTRY_USER": "theregistryuser",
                    "REGISTRY_PW": "some_secret_value",
                    "REGISTRY_SSL": "True",
                    "REGISTRY_URL": "registry.osparc-master.speag.com",
                }
            ],
        }
    )
