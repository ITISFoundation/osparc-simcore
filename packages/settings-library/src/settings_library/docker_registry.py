from functools import cached_property
from typing import Any, Self

from pydantic import (
    AnyHttpUrl,
    Field,
    SecretStr,
    TypeAdapter,
    field_validator,
    model_validator,
)
from pydantic_settings import SettingsConfigDict

from .base import BaseCustomSettings


class RegistrySettings(BaseCustomSettings):
    REGISTRY_AUTH: bool = Field(..., description="do registry authentication")
    REGISTRY_PATH: str | None = Field(
        default=None,
        # This is useful in case of a local registry, where the registry url (path) is relative to the host docker engine"
        description="development mode only, in case a local registry is used - "
        "this is the hostname to the docker registry as seen from inside the container",
    )
    # NOTE: name is missleading, http or https protocol are not included
    REGISTRY_URL: str = Field(
        ...,
        description="hostname of docker registry (without protocol but with port if available) - "
        "typically used by the host machine docker engine",
        min_length=1,
    )

    REGISTRY_USER: str = Field(
        ..., description="username to access the docker registry"
    )
    REGISTRY_PW: SecretStr = Field(
        ..., description="password to access the docker registry"
    )
    REGISTRY_SSL: bool = Field(
        ..., description="True if docker registry is using HTTPS protocol"
    )

    @field_validator("REGISTRY_PATH", mode="before")
    @classmethod
    def _escape_none_string(cls, v) -> Any | None:
        return None if v == "None" else v

    @model_validator(mode="after")
    def check_registry_authentication(self: Self) -> Self:
        if self.REGISTRY_AUTH and any(
            not v for v in (self.REGISTRY_USER, self.REGISTRY_PW)
        ):
            msg = "If REGISTRY_AUTH is True, both REGISTRY_USER and REGISTRY_PW must be provided"
            raise ValueError(msg)
        return self

    @cached_property
    def resolved_registry_url(self) -> str:
        return self.REGISTRY_PATH or self.REGISTRY_URL

    @cached_property
    def api_url(self) -> str:
        return f"{self.REGISTRY_URL}/v2"

    @cached_property
    def registry_url_for_docker_engine(self) -> AnyHttpUrl:
        """returns the full URL to the Docker Registry for use by docker engine"""
        protocol = "https" if self.REGISTRY_SSL else "http"
        return TypeAdapter(AnyHttpUrl).validate_python(
            f"{protocol}://{self.REGISTRY_URL}"
        )

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
