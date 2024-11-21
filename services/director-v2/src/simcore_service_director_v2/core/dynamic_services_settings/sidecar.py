import logging
import warnings
from enum import Enum
from pathlib import Path
from typing import Annotated

from models_library.basic_types import BootModeEnum, PortInt
from models_library.docker import DockerPlacementConstraint
from models_library.utils.common_validators import (
    ensure_unique_dict_values_validator,
    ensure_unique_list_values_validator,
)
from pydantic import AliasChoices, Field, PositiveInt, ValidationInfo, field_validator
from settings_library.aws_s3_cli import AwsS3CliSettings
from settings_library.base import BaseCustomSettings
from settings_library.efs import AwsEfsSettings
from settings_library.r_clone import RCloneSettings as SettingsLibraryRCloneSettings
from settings_library.utils_logging import MixinLoggingSettings
from settings_library.utils_service import DEFAULT_FASTAPI_PORT

from ...constants import DYNAMIC_SIDECAR_DOCKER_IMAGE_RE

_logger = logging.getLogger(__name__)


class VFSCacheMode(str, Enum):
    __slots__ = ()

    OFF = "off"
    MINIMAL = "minimal"
    WRITES = "writes"
    FULL = "full"


class RCloneSettings(SettingsLibraryRCloneSettings):
    R_CLONE_DIR_CACHE_TIME_SECONDS: PositiveInt = Field(
        10,
        description="time to cache directory entries for",
    )
    R_CLONE_POLL_INTERVAL_SECONDS: PositiveInt = Field(
        9,
        description="time to wait between polling for changes",
    )
    R_CLONE_VFS_CACHE_MODE: VFSCacheMode = Field(
        VFSCacheMode.MINIMAL,  # SEE https://rclone.org/commands/rclone_mount/#vfs-file-caching
        description="VFS operation mode, defines how and when the disk cache is synced",
    )

    @field_validator("R_CLONE_POLL_INTERVAL_SECONDS")
    @classmethod
    def enforce_r_clone_requirement(cls, v: int, info: ValidationInfo) -> PositiveInt:
        dir_cache_time = info.data["R_CLONE_DIR_CACHE_TIME_SECONDS"]
        if v >= dir_cache_time:
            msg = f"R_CLONE_POLL_INTERVAL_SECONDS={v} must be lower than R_CLONE_DIR_CACHE_TIME_SECONDS={dir_cache_time}"
            raise ValueError(msg)
        return v


class PlacementSettings(BaseCustomSettings):
    # This is just a service placement constraint, see
    # https://docs.docker.com/engine/swarm/services/#control-service-placement.
    DIRECTOR_V2_SERVICES_CUSTOM_CONSTRAINTS: list[DockerPlacementConstraint] = Field(
        default_factory=list,
        examples=['["node.labels.region==east", "one!=yes"]'],
    )

    DIRECTOR_V2_GENERIC_RESOURCE_PLACEMENT_CONSTRAINTS_SUBSTITUTIONS: dict[
        str, DockerPlacementConstraint
    ] = Field(
        default_factory=dict,
        description=(
            "Use placement constraints in place of generic resources, for details "
            "see https://github.com/ITISFoundation/osparc-simcore/issues/5250 "
            "When `None` (default), uses generic resources"
        ),
        examples=['{"AIRAM": "node.labels.custom==true"}'],
    )

    _unique_custom_constraints = field_validator(
        "DIRECTOR_V2_SERVICES_CUSTOM_CONSTRAINTS",
    )(ensure_unique_list_values_validator)

    _unique_resource_placement_constraints_substitutions = field_validator(
        "DIRECTOR_V2_GENERIC_RESOURCE_PLACEMENT_CONSTRAINTS_SUBSTITUTIONS",
    )(ensure_unique_dict_values_validator)

    @field_validator("DIRECTOR_V2_GENERIC_RESOURCE_PLACEMENT_CONSTRAINTS_SUBSTITUTIONS")
    @classmethod
    def warn_if_any_values_provided(cls, value: dict) -> dict:
        if len(value) > 0:
            warnings.warn(  # noqa: B028
                "Generic resources will be replaced by the following "
                f"placement constraints {value}. This is a workaround "
                "for https://github.com/moby/swarmkit/pull/3162",
                UserWarning,
            )
        return value


class DynamicSidecarSettings(BaseCustomSettings, MixinLoggingSettings):
    DYNAMIC_SIDECAR_ENDPOINT_SPECS_MODE_DNSRR_ENABLED: bool = Field(  # doc: https://docs.docker.com/engine/swarm/networking/#configure-service-discovery
        default=False,
        validation_alias=AliasChoices(
            "DYNAMIC_SIDECAR_ENDPOINT_SPECS_MODE_DNSRR_ENABLED"
        ),
        description="dynamic-sidecar's service 'endpoint_spec' with {'Mode': 'dnsrr'}",
    )
    DYNAMIC_SIDECAR_SC_BOOT_MODE: Annotated[
        BootModeEnum,
        Field(
            ...,
            description="Boot mode used for the dynamic-sidecar services"
            "By defaults, it uses the same boot mode set for the director-v2",
            validation_alias=AliasChoices(
                "DYNAMIC_SIDECAR_SC_BOOT_MODE", "SC_BOOT_MODE"
            ),
        ),
    ]

    DYNAMIC_SIDECAR_LOG_LEVEL: str = Field(
        "WARNING",
        description="log level of the dynamic sidecar"
        "If defined, it captures global env vars LOG_LEVEL and LOGLEVEL from the director-v2 service",
        validation_alias=AliasChoices(
            "DYNAMIC_SIDECAR_LOG_LEVEL", "LOG_LEVEL", "LOGLEVEL"
        ),
    )

    DYNAMIC_SIDECAR_IMAGE: str = Field(
        ...,
        pattern=DYNAMIC_SIDECAR_DOCKER_IMAGE_RE,
        description="used by the director to start a specific version of the dynamic-sidecar",
    )

    DYNAMIC_SIDECAR_R_CLONE_SETTINGS: RCloneSettings = Field(
        json_schema_extra={"auto_default_from_env": True}
    )

    DYNAMIC_SIDECAR_AWS_S3_CLI_SETTINGS: AwsS3CliSettings | None = Field(
        json_schema_extra={"auto_default_from_env": True}
    )
    DYNAMIC_SIDECAR_EFS_SETTINGS: AwsEfsSettings | None = Field(
        json_schema_extra={"auto_default_from_env": True}
    )

    DYNAMIC_SIDECAR_PLACEMENT_SETTINGS: PlacementSettings = Field(
        json_schema_extra={"auto_default_from_env": True}
    )

    #
    # DEVELOPMENT ONLY config
    #

    DYNAMIC_SIDECAR_MOUNT_PATH_DEV: Path | None = Field(
        None,
        description="Host path to the dynamic-sidecar project. Used as source path to mount to the dynamic-sidecar [DEVELOPMENT ONLY]",
        examples=["osparc-simcore/services/dynamic-sidecar"],
    )

    DYNAMIC_SIDECAR_PORT: PortInt = Field(
        DEFAULT_FASTAPI_PORT,
        description="port on which the webserver for the dynamic-sidecar is exposed [DEVELOPMENT ONLY]",
    )

    DYNAMIC_SIDECAR_EXPOSE_PORT: bool = Field(
        default=False,
        description="Publishes the service on localhost for debuging and testing [DEVELOPMENT ONLY]"
        "Can be used to access swagger doc from the host as http://127.0.0.1:30023/dev/doc "
        "where 30023 is the host published port",
        validate_default=True,
    )

    @field_validator("DYNAMIC_SIDECAR_MOUNT_PATH_DEV", mode="before")
    @classmethod
    def auto_disable_if_production(cls, v, info: ValidationInfo):
        if (
            v
            and info.data.get("DYNAMIC_SIDECAR_SC_BOOT_MODE") == BootModeEnum.PRODUCTION
        ):
            _logger.warning(
                "In production DYNAMIC_SIDECAR_MOUNT_PATH_DEV cannot be set to %s, enforcing None",
                v,
            )
            return None
        return v

    @field_validator("DYNAMIC_SIDECAR_EXPOSE_PORT", mode="before")
    @classmethod
    def auto_enable_if_development(cls, v, info: ValidationInfo):
        if (
            boot_mode := info.data.get("DYNAMIC_SIDECAR_SC_BOOT_MODE")
        ) and boot_mode.is_devel_mode():
            # Can be used to access swagger doc from the host as http://127.0.0.1:30023/dev/doc
            return True
        return v

    @field_validator("DYNAMIC_SIDECAR_IMAGE", mode="before")
    @classmethod
    def strip_leading_slashes(cls, v: str) -> str:
        return v.lstrip("/")

    @field_validator("DYNAMIC_SIDECAR_LOG_LEVEL")
    @classmethod
    def _validate_log_level(cls, value) -> str:
        log_level: str = cls.validate_log_level(value)
        return log_level
