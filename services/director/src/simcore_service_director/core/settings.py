import datetime
import warnings
from typing import cast

from fastapi import FastAPI
from models_library.basic_types import LogLevel, PortInt, VersionTag
from pydantic import AliasChoices, Field, NonNegativeInt, PositiveInt, field_validator
from servicelib.logging_utils_filtering import LoggerName, MessageSubstring
from settings_library.application import BaseApplicationSettings
from settings_library.docker_registry import RegistrySettings
from settings_library.postgres import PostgresSettings
from settings_library.tracing import TracingSettings
from settings_library.utils_logging import MixinLoggingSettings

from .._meta import API_VERSION, API_VTAG, APP_NAME


class ApplicationSettings(BaseApplicationSettings, MixinLoggingSettings):
    API_VERSION: str = API_VERSION
    APP_NAME: str = APP_NAME
    API_VTAG: VersionTag = API_VTAG

    DIRECTOR_DEBUG: bool = Field(
        default=False,
        description="Debug mode",
        validation_alias=AliasChoices("DIRECTOR_DEBUG", "DEBUG"),
    )
    DIRECTOR_REMOTE_DEBUG_PORT: PortInt = 3000

    DIRECTOR_LOGLEVEL: LogLevel = Field(
        ..., validation_alias=AliasChoices("DIRECTOR_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL")
    )
    DIRECTOR_LOG_FORMAT_LOCAL_DEV_ENABLED: bool = Field(
        ...,
        validation_alias=AliasChoices(
            "DIRECTOR_LOG_FORMAT_LOCAL_DEV_ENABLED",
            "LOG_FORMAT_LOCAL_DEV_ENABLED",
        ),
        description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
    )
    DIRECTOR_LOG_FILTER_MAPPING: dict[LoggerName, list[MessageSubstring]] = Field(
        default_factory=dict,
        validation_alias=AliasChoices(
            "DIRECTOR_LOG_FILTER_MAPPING", "LOG_FILTER_MAPPING"
        ),
        description="is a dictionary that maps specific loggers (such as 'uvicorn.access' or 'gunicorn.access') to a list of log message patterns that should be filtered out.",
    )
    DIRECTOR_TRACING: TracingSettings | None = Field(
        description="settings for opentelemetry tracing",
        json_schema_extra={"auto_default_from_env": True},
    )

    DIRECTOR_DEFAULT_MAX_NANO_CPUS: NonNegativeInt = Field(default=0)
    DIRECTOR_DEFAULT_MAX_MEMORY: NonNegativeInt = Field(default=0)
    DIRECTOR_REGISTRY_CACHING: bool = Field(
        ..., description="cache the docker registry internally"
    )
    DIRECTOR_REGISTRY_CACHING_TTL: datetime.timedelta = Field(
        ..., description="cache time to live value (defaults to 15 minutes)"
    )

    DIRECTOR_SERVICES_CUSTOM_CONSTRAINTS: str | None

    DIRECTOR_GENERIC_RESOURCE_PLACEMENT_CONSTRAINTS_SUBSTITUTIONS: dict[str, str]

    DIRECTOR_SERVICES_RESTART_POLICY_MAX_ATTEMPTS: int = 10
    DIRECTOR_SERVICES_RESTART_POLICY_DELAY_S: int = 12
    DIRECTOR_SERVICES_STATE_MONITOR_S: int = 8

    DIRECTOR_TRAEFIK_SIMCORE_ZONE: str = Field(
        ...,
        validation_alias=AliasChoices(
            "DIRECTOR_TRAEFIK_SIMCORE_ZONE", "TRAEFIK_SIMCORE_ZONE"
        ),
    )

    DIRECTOR_REGISTRY: RegistrySettings = Field(
        description="settings for the private registry deployed with the platform",
        json_schema_extra={"auto_default_from_env": True},
    )

    DIRECTOR_POSTGRES: PostgresSettings = Field(
        ..., json_schema_extra={"auto_default_from_env": True}
    )
    STORAGE_ENDPOINT: str = Field(..., description="storage endpoint without scheme")

    DIRECTOR_PUBLISHED_HOST_NAME: str = Field(
        ...,
        validation_alias=AliasChoices(
            "DIRECTOR_PUBLISHED_HOST_NAME", "PUBLISHED_HOST_NAME"
        ),
    )

    DIRECTOR_SWARM_STACK_NAME: str = Field(
        ...,
        validation_alias=AliasChoices("DIRECTOR_SWARM_STACK_NAME", "SWARM_STACK_NAME"),
    )

    DIRECTOR_SIMCORE_SERVICES_NETWORK_NAME: str | None = Field(
        # used to find the right network name
        ...,
        validation_alias=AliasChoices(
            "DIRECTOR_SIMCORE_SERVICES_NETWORK_NAME",
            "SIMCORE_SERVICES_NETWORK_NAME",
        ),
    )

    DIRECTOR_MONITORING_ENABLED: bool = Field(
        ...,
        validation_alias=AliasChoices(
            "DIRECTOR_MONITORING_ENABLED", "MONITORING_ENABLED"
        ),
    )

    DIRECTOR_REGISTRY_CLIENT_MAX_CONCURRENT_CALLS: PositiveInt = 20
    DIRECTOR_REGISTRY_CLIENT_MAX_NUMBER_OF_RETRIEVED_OBJECTS: PositiveInt = 30

    @field_validator("DIRECTOR_GENERIC_RESOURCE_PLACEMENT_CONSTRAINTS_SUBSTITUTIONS")
    @classmethod
    def _validate_substitutions(cls, v):
        if v:
            warnings.warn(  # noqa: B028
                "Generic resources will be replaced by the following "
                f"placement constraints {v}. This is a workaround "
                "for https://github.com/moby/swarmkit/pull/3162",
                UserWarning,
            )
        if len(v) != len(set(v.values())):
            msg = f"Dictionary values must be unique, provided: {v}"
            raise ValueError(msg)

        return v

    @field_validator("DIRECTOR_LOGLEVEL", mode="before")
    @classmethod
    def _valid_log_level(cls, value: str) -> str:
        return cls.validate_log_level(value)


def get_application_settings(app: FastAPI) -> ApplicationSettings:
    return cast(ApplicationSettings, app.state.settings)
