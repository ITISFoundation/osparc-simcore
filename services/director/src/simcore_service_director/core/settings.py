import datetime
import warnings
from functools import cached_property
from typing import Annotated, cast

from common_library.basic_types import DEFAULT_FACTORY
from common_library.logging.logging_utils_filtering import LoggerName, MessageSubstring
from fastapi import FastAPI
from models_library.basic_types import LogLevel, PortInt, VersionTag
from models_library.docker import (
    OSPARC_CUSTOM_DOCKER_PLACEMENT_CONSTRAINTS_LABEL_KEYS,
    DockerLabelKey,
    DockerPlacementConstraint,
)
from pydantic import (
    AliasChoices,
    Field,
    Json,
    NonNegativeInt,
    PositiveInt,
    field_validator,
)
from servicelib.logging_utils import LogLevelInt
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

    DIRECTOR_DEBUG: Annotated[
        bool,
        Field(
            description="Debug mode",
            validation_alias=AliasChoices("DIRECTOR_DEBUG", "DEBUG"),
        ),
    ] = False
    DIRECTOR_REMOTE_DEBUG_PORT: PortInt = 3000

    DIRECTOR_LOG_LEVEL: Annotated[
        LogLevel,
        Field(
            validation_alias=AliasChoices("DIRECTOR_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL")
        ),
    ]
    DIRECTOR_LOG_FORMAT_LOCAL_DEV_ENABLED: Annotated[
        bool,
        Field(
            validation_alias=AliasChoices(
                "DIRECTOR_LOG_FORMAT_LOCAL_DEV_ENABLED", "LOG_FORMAT_LOCAL_DEV_ENABLED"
            ),
            description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
        ),
    ]
    DIRECTOR_LOG_FILTER_MAPPING: Annotated[
        dict[LoggerName, list[MessageSubstring]],
        Field(
            validation_alias=AliasChoices(
                "DIRECTOR_LOG_FILTER_MAPPING", "LOG_FILTER_MAPPING"
            ),
            description="is a dictionary that maps specific loggers (such as 'uvicorn.access' or 'gunicorn.access') to a list of log message patterns that should be filtered out.",
        ),
    ] = DEFAULT_FACTORY
    DIRECTOR_TRACING: Annotated[
        TracingSettings | None,
        Field(
            description="settings for opentelemetry tracing",
            json_schema_extra={"auto_default_from_env": True},
        ),
    ] = None

    DIRECTOR_DEFAULT_MAX_NANO_CPUS: NonNegativeInt = 0
    DIRECTOR_DEFAULT_MAX_MEMORY: NonNegativeInt = 0
    DIRECTOR_REGISTRY_CACHING: Annotated[
        bool, Field(description="cache the docker registry internally")
    ]
    DIRECTOR_REGISTRY_CACHING_TTL: Annotated[
        datetime.timedelta,
        Field(description="cache time to live value (defaults to 15 minutes)"),
    ]

    DIRECTOR_SERVICES_CUSTOM_PLACEMENT_CONSTRAINTS: Annotated[
        list[DockerPlacementConstraint],
        Field(examples=['["node.labels.region==east", "one!=yes"]']),
    ] = DEFAULT_FACTORY
    DIRECTOR_SERVICES_CUSTOM_LABELS: Annotated[
        dict[DockerLabelKey, str],
        Field(examples=['{"com.example.description":"Accounting webapp"}']),
    ] = DEFAULT_FACTORY

    DIRECTOR_OSPARC_CUSTOM_DOCKER_PLACEMENT_CONSTRAINTS: Annotated[
        Json[dict[str, str]],
        Field(
            default_factory=lambda: "{}",
            description="Dynamic placement labels for service node placement. Keys must be in CUSTOM_PLACEMENT_LABEL_KEYS.",
            examples=['{"product_name": "osparc", "user_id": "{user_id}"}'],
        ),
    ] = DEFAULT_FACTORY

    DIRECTOR_GENERIC_RESOURCE_PLACEMENT_CONSTRAINTS_SUBSTITUTIONS: dict[str, str]

    DIRECTOR_SERVICES_RESTART_POLICY_MAX_ATTEMPTS: int = 10
    DIRECTOR_SERVICES_RESTART_POLICY_DELAY_S: int = 12
    DIRECTOR_SERVICES_STATE_MONITOR_S: int = 8

    @field_validator("DIRECTOR_OSPARC_CUSTOM_DOCKER_PLACEMENT_CONSTRAINTS")
    @classmethod
    def _validate_osparc_custom_placement_constraints_keys(
        cls, v: dict[str, str]
    ) -> dict[str, str]:
        invalid_keys = set(v.keys()) - set(
            OSPARC_CUSTOM_DOCKER_PLACEMENT_CONSTRAINTS_LABEL_KEYS
        )
        if invalid_keys:
            msg = f"Invalid placement label keys {invalid_keys}. Must be one of {OSPARC_CUSTOM_DOCKER_PLACEMENT_CONSTRAINTS_LABEL_KEYS}"
            raise ValueError(msg)
        return v

    DIRECTOR_TRAEFIK_SIMCORE_ZONE: Annotated[
        str,
        Field(
            validation_alias=AliasChoices(
                "DIRECTOR_TRAEFIK_SIMCORE_ZONE", "TRAEFIK_SIMCORE_ZONE"
            )
        ),
    ]

    DIRECTOR_REGISTRY: Annotated[
        RegistrySettings,
        Field(
            description="settings for the private registry deployed with the platform",
            json_schema_extra={"auto_default_from_env": True},
        ),
    ]

    DIRECTOR_POSTGRES: Annotated[
        PostgresSettings, Field(json_schema_extra={"auto_default_from_env": True})
    ]
    STORAGE_ENDPOINT: Annotated[
        str, Field(description="storage endpoint without scheme")
    ]

    DIRECTOR_PUBLISHED_HOST_NAME: Annotated[
        str,
        Field(
            validation_alias=AliasChoices(
                "DIRECTOR_PUBLISHED_HOST_NAME", "PUBLISHED_HOST_NAME"
            )
        ),
    ]

    DIRECTOR_SWARM_STACK_NAME: Annotated[
        str,
        Field(
            validation_alias=AliasChoices(
                "DIRECTOR_SWARM_STACK_NAME", "SWARM_STACK_NAME"
            )
        ),
    ]

    DIRECTOR_SIMCORE_SERVICES_NETWORK_NAME: Annotated[
        str | None,
        Field(
            validation_alias=AliasChoices(
                "DIRECTOR_SIMCORE_SERVICES_NETWORK_NAME",
                "SIMCORE_SERVICES_NETWORK_NAME",
            )
        ),
    ]

    DIRECTOR_MONITORING_ENABLED: Annotated[
        bool,
        Field(
            validation_alias=AliasChoices(
                "DIRECTOR_MONITORING_ENABLED", "MONITORING_ENABLED"
            )
        ),
    ]

    DIRECTOR_REGISTRY_CLIENT_MAX_KEEPALIVE_CONNECTIONS: NonNegativeInt = 5
    DIRECTOR_REGISTRY_CLIENT_TIMEOUT: datetime.timedelta = datetime.timedelta(
        seconds=20
    )
    DIRECTOR_REGISTRY_CLIENT_MAX_CONCURRENT_CALLS: PositiveInt = 20
    DIRECTOR_REGISTRY_CLIENT_MAX_NUMBER_OF_RETRIEVED_OBJECTS: PositiveInt = 30

    @field_validator("DIRECTOR_REGISTRY_CLIENT_TIMEOUT")
    @classmethod
    def _check_positive(cls, value: datetime.timedelta) -> datetime.timedelta:
        if value.total_seconds() < 0:
            msg = "DIRECTOR_REGISTRY_CLIENT_TIMEOUT must be positive"
            raise ValueError(msg)
        return value

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

    @cached_property
    def log_level(self) -> LogLevelInt:
        """override"""
        return cast(LogLevelInt, self.DIRECTOR_LOG_LEVEL)


def get_application_settings(app: FastAPI) -> ApplicationSettings:
    return cast(ApplicationSettings, app.state.settings)
