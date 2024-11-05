import datetime
import warnings
from typing import cast

from fastapi import FastAPI
from models_library.basic_types import (
    BootModeEnum,
    BuildTargetEnum,
    LogLevel,
    PortInt,
    VersionTag,
)
from pydantic import ByteSize, Field, PositiveInt, parse_obj_as, validator
from servicelib.logging_utils_filtering import LoggerName, MessageSubstring
from settings_library.base import BaseCustomSettings
from settings_library.docker_registry import RegistrySettings
from settings_library.postgres import PostgresSettings
from settings_library.tracing import TracingSettings
from settings_library.utils_logging import MixinLoggingSettings

from .._meta import API_VERSION, API_VTAG, APP_NAME


class ApplicationSettings(BaseCustomSettings, MixinLoggingSettings):
    # CODE STATICS ---------------------------------------------------------
    API_VERSION: str = API_VERSION
    APP_NAME: str = APP_NAME
    API_VTAG: VersionTag = API_VTAG

    # IMAGE BUILDTIME ------------------------------------------------------
    # @Makefile
    SC_BUILD_DATE: str | None = None
    SC_BUILD_TARGET: BuildTargetEnum | None = None
    SC_VCS_REF: str | None = None
    SC_VCS_URL: str | None = None

    # @Dockerfile
    SC_BOOT_MODE: BootModeEnum | None = None
    SC_BOOT_TARGET: BuildTargetEnum | None = None
    SC_HEALTHCHECK_TIMEOUT: PositiveInt | None = Field(
        None,
        description="If a single run of the check takes longer than timeout seconds "
        "then the check is considered to have failed."
        "It takes retries consecutive failures of the health check for the container to be considered unhealthy.",
    )
    SC_USER_ID: int | None = None
    SC_USER_NAME: str | None = None

    # RUNTIME  -----------------------------------------------------------
    DIRECTOR_DEBUG: bool = Field(
        default=False, description="Debug mode", env=["DIRECTOR_DEBUG", "DEBUG"]
    )
    DIRECTOR_REMOTE_DEBUG_PORT: PortInt = PortInt(3000)

    DIRECTOR_LOGLEVEL: LogLevel = Field(
        LogLevel.INFO, env=["DIRECTOR_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"]
    )
    DIRECTOR_LOG_FORMAT_LOCAL_DEV_ENABLED: bool = Field(
        default=False,
        env=[
            "DIRECTOR_LOG_FORMAT_LOCAL_DEV_ENABLED",
            "LOG_FORMAT_LOCAL_DEV_ENABLED",
        ],
        description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
    )
    DIRECTOR_LOG_FILTER_MAPPING: dict[LoggerName, list[MessageSubstring]] = Field(
        default_factory=dict,
        env=["DIRECTOR_LOG_FILTER_MAPPING", "LOG_FILTER_MAPPING"],
        description="is a dictionary that maps specific loggers (such as 'uvicorn.access' or 'gunicorn.access') to a list of log message patterns that should be filtered out.",
    )
    DIRECTOR_TRACING: TracingSettings | None = Field(
        auto_default_from_env=True, description="settings for opentelemetry tracing"
    )

    # migrated settings
    DIRECTOR_DEFAULT_MAX_NANO_CPUS: PositiveInt = Field(
        default=1 * pow(10, 9),
        env=["DIRECTOR_DEFAULT_MAX_NANO_CPUS", "DEFAULT_MAX_NANO_CPUS"],
    )
    DIRECTOR_DEFAULT_MAX_MEMORY: PositiveInt = Field(
        default=parse_obj_as(ByteSize, "2GiB"),
        env=["DIRECTOR_DEFAULT_MAX_MEMORY", "DEFAULT_MAX_MEMORY"],
    )
    DIRECTOR_REGISTRY_CACHING: bool = Field(
        default=True, description="cache the docker registry internally"
    )
    DIRECTOR_REGISTRY_CACHING_TTL: datetime.timedelta = Field(
        default=datetime.timedelta(minutes=15),
        description="cache time to live value (defaults to 15 minutes)",
    )
    DIRECTOR_SERVICES_CUSTOM_CONSTRAINTS: str = ""

    DIRECTOR_GENERIC_RESOURCE_PLACEMENT_CONSTRAINTS_SUBSTITUTIONS: dict[
        str, str
    ] = Field(default_factory=dict)
    DIRECTOR_SELF_SIGNED_SSL_SECRET_ID: str = ""
    DIRECTOR_SELF_SIGNED_SSL_SECRET_NAME: str = ""
    DIRECTOR_SELF_SIGNED_SSL_FILENAME: str = ""

    DIRECTOR_SERVICES_RESTART_POLICY_MAX_ATTEMPTS: int = 10
    DIRECTOR_SERVICES_RESTART_POLICY_DELAY_S: int = 12
    DIRECTOR_SERVICES_STATE_MONITOR_S: int = 8

    DIRECTOR_TRAEFIK_SIMCORE_ZONE: str = Field(
        default="internal_simcore_stack",
        env=["DIRECTOR_TRAEFIK_SIMCORE_ZONE", "TRAEFIK_SIMCORE_ZONE"],
    )

    DIRECTOR_REGISTRY: RegistrySettings = Field(
        auto_default_from_env=True,
        description="settings for the private registry deployed with the platform",
    )

    DIRECTOR_EXTRA_HOSTS_SUFFIX: str = Field(
        default="undefined", env=["DIRECTOR_EXTRA_HOSTS_SUFFIX", "EXTRA_HOSTS_SUFFIX"]
    )

    DIRECTOR_POSTGRES: PostgresSettings = Field(auto_default_from_env=True)
    STORAGE_ENDPOINT: str = Field(..., description="storage endpoint without scheme")

    DIRECTOR_PUBLISHED_HOST_NAME: str = Field(
        default="", env=["DIRECTOR_PUBLISHED_HOST_NAME", "PUBLISHED_HOST_NAME"]
    )

    DIRECTOR_SWARM_STACK_NAME: str = Field(
        default="undefined-please-check",
        env=["DIRECTOR_SWARM_STACK_NAME", "SWARM_STACK_NAME"],
    )

    # used to find the right network name
    DIRECTOR_SIMCORE_SERVICES_NETWORK_NAME: str | None = Field(
        default=None,
        env=["DIRECTOR_SIMCORE_SERVICES_NETWORK_NAME", "SIMCORE_SERVICES_NETWORK_NAME"],
    )
    # useful when developing with an alternative registry namespace

    DIRECTOR_MONITORING_ENABLED: bool = Field(
        default=False, env=["DIRECTOR_MONITORING_ENABLED", "MONITORING_ENABLED"]
    )

    @validator("DIRECTOR_GENERIC_RESOURCE_PLACEMENT_CONSTRAINTS_SUBSTITUTIONS")
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

    @validator("DIRECTOR_LOGLEVEL", pre=True)
    @classmethod
    def _valid_log_level(cls, value: str) -> str:
        return cls.validate_log_level(value)


def get_application_settings(app: FastAPI) -> ApplicationSettings:
    return cast(ApplicationSettings, app.state.settings)
