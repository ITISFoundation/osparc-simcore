import logging
import warnings
from pathlib import Path
from typing import Annotated

from common_library.basic_types import DEFAULT_FACTORY, BootModeEnum
from models_library.docker import (
    OSPARC_CUSTOM_DOCKER_PLACEMENT_CONSTRAINTS_LABEL_KEYS,
    DockerLabelKey,
    DockerPlacementConstraint,
)
from models_library.utils.common_validators import (
    ensure_unique_dict_values_validator,
    ensure_unique_list_values_validator,
)
from pydantic import (
    AliasChoices,
    Field,
    Json,
    ValidationInfo,
    field_validator,
)
from settings_library.base import BaseCustomSettings
from settings_library.basic_types import PortInt
from settings_library.efs import AwsEfsSettings
from settings_library.r_clone import RCloneSettings
from settings_library.utils_logging import MixinLoggingSettings
from settings_library.utils_service import DEFAULT_FASTAPI_PORT

from ...constants import DYNAMIC_SIDECAR_DOCKER_IMAGE_RE

_logger = logging.getLogger(__name__)


class PlacementSettings(BaseCustomSettings):
    DIRECTOR_V2_SERVICES_CUSTOM_PLACEMENT_CONSTRAINTS: Annotated[
        list[DockerPlacementConstraint],
        Field(
            default_factory=list, examples=['["node.labels.region==east", "one!=yes"]']
        ),
    ] = DEFAULT_FACTORY

    DIRECTOR_V2_GENERIC_RESOURCE_PLACEMENT_CONSTRAINTS_SUBSTITUTIONS: Annotated[
        dict[str, DockerPlacementConstraint],
        Field(
            default_factory=dict,
            description="Use placement constraints in place of generic resources, for details see https://github.com/ITISFoundation/osparc-simcore/issues/5250 When `None` (default), uses generic resources",
            examples=['{"AIRAM": "node.labels.custom==true"}'],
        ),
    ] = DEFAULT_FACTORY

    DIRECTOR_V2_DYNAMIC_SIDECAR_OSPARC_CUSTOM_DOCKER_PLACEMENT_CONSTRAINTS: Annotated[
        Json[dict[DockerPlacementConstraint, str]],
        Field(
            default_factory=lambda: "{}",
            description="Dynamic sidecar custom placement labels for flexible node targeting. Keys must be from: "
            + ", ".join(OSPARC_CUSTOM_DOCKER_PLACEMENT_CONSTRAINTS_LABEL_KEYS)
            + ". Values are template strings supporting: {user_id}, {project_id}, {product_name}, {node_id}, {group_id}, {wallet_id}. Missing template values cause the label to be skipped.",
            examples=['{{"product-name": "platform", "user-id": "user_{user_id}"}}'],
        ),
    ] = DEFAULT_FACTORY

    _unique_custom_constraints = field_validator(
        "DIRECTOR_V2_SERVICES_CUSTOM_PLACEMENT_CONSTRAINTS",
    )(ensure_unique_list_values_validator)

    _unique_resource_placement_constraints_substitutions = field_validator(
        "DIRECTOR_V2_GENERIC_RESOURCE_PLACEMENT_CONSTRAINTS_SUBSTITUTIONS",
    )(ensure_unique_dict_values_validator)

    @field_validator(
        "DIRECTOR_V2_DYNAMIC_SIDECAR_OSPARC_CUSTOM_DOCKER_PLACEMENT_CONSTRAINTS"
    )
    @classmethod
    def validate_osparc_custom_docker_placement_constraints_keys(
        cls, value: dict[str, str]
    ) -> dict[str, str]:
        """Validate that all keys are in the allowed set."""
        invalid_keys = set(value.keys()) - set(
            OSPARC_CUSTOM_DOCKER_PLACEMENT_CONSTRAINTS_LABEL_KEYS
        )
        if invalid_keys:
            msg = (
                f"Invalid custom placement label keys: {invalid_keys}. "
                f"Allowed keys: {set(OSPARC_CUSTOM_DOCKER_PLACEMENT_CONSTRAINTS_LABEL_KEYS)}"
            )
            raise ValueError(msg)
        return value

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
    DYNAMIC_SIDECAR_ENDPOINT_SPECS_MODE_DNSRR_ENABLED: Annotated[
        bool,
        Field(
            validation_alias=AliasChoices(
                "DYNAMIC_SIDECAR_ENDPOINT_SPECS_MODE_DNSRR_ENABLED"
            ),
            description="dynamic-sidecar's service 'endpoint_spec' with {'Mode': 'dnsrr'}",
        ),
    ] = False
    DYNAMIC_SIDECAR_SC_BOOT_MODE: Annotated[
        BootModeEnum,
        Field(
            description="Boot mode used for the dynamic-sidecar services By defaults, it uses the same boot mode set for the director-v2",
            validation_alias=AliasChoices(
                "DYNAMIC_SIDECAR_SC_BOOT_MODE", "SC_BOOT_MODE"
            ),
        ),
    ]

    DYNAMIC_SIDECAR_LOG_LEVEL: Annotated[
        str,
        Field(
            description="log level of the dynamic sidecar If defined, it captures global env vars LOG_LEVEL and LOGLEVEL from the director-v2 service",
            validation_alias=AliasChoices(
                "DYNAMIC_SIDECAR_LOG_LEVEL", "LOG_LEVEL", "LOGLEVEL"
            ),
        ),
    ] = "WARNING"

    DYNAMIC_SIDECAR_IMAGE: Annotated[
        str,
        Field(
            pattern=DYNAMIC_SIDECAR_DOCKER_IMAGE_RE,
            description="used by the director to start a specific version of the dynamic-sidecar",
        ),
    ]

    DYNAMIC_SIDECAR_R_CLONE_SETTINGS: Annotated[
        RCloneSettings, Field(json_schema_extra={"auto_default_from_env": True})
    ]

    DYNAMIC_SIDECAR_EFS_SETTINGS: Annotated[
        AwsEfsSettings | None, Field(json_schema_extra={"auto_default_from_env": True})
    ] = None

    DYNAMIC_SIDECAR_PLACEMENT_SETTINGS: Annotated[
        PlacementSettings, Field(json_schema_extra={"auto_default_from_env": True})
    ]

    DYNAMIC_SIDECAR_CUSTOM_LABELS: Annotated[
        dict[DockerLabelKey, str],
        Field(
            default_factory=dict,
            description="Custom labels to add to the dynamic-sidecar service",
            examples=[{"label_key": "label_value"}],
        ),
    ] = DEFAULT_FACTORY

    DYNAMIC_SIDECAR_MOUNT_PATH_DEV: Annotated[
        Path | None,
        Field(
            description="Host path to the dynamic-sidecar project. Used as source path to mount to the dynamic-sidecar [DEVELOPMENT ONLY]",
            examples=["osparc-simcore/services/dynamic-sidecar"],
        ),
    ] = None

    DYNAMIC_SIDECAR_PORT: Annotated[
        PortInt,
        Field(
            description="port on which the webserver for the dynamic-sidecar is exposed [DEVELOPMENT ONLY]"
        ),
    ] = DEFAULT_FASTAPI_PORT

    DYNAMIC_SIDECAR_EXPOSE_PORT: Annotated[
        bool,
        Field(
            description="Publishes the service on localhost for debugging and testing [DEVELOPMENT ONLY] Can be used to access swagger doc from the host as http://127.0.0.1:30023/dev/doc where 30023 is the host published port",
            validate_default=True,
        ),
    ] = False

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
