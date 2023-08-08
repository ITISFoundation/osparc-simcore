import warnings
from functools import lru_cache
from pathlib import Path
from typing import cast

from models_library.basic_types import BootModeEnum, PortInt
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.services import RunID
from models_library.users import UserID
from pydantic import Field, PositiveInt, validator
from settings_library.base import BaseCustomSettings
from settings_library.docker_registry import RegistrySettings
from settings_library.r_clone import RCloneSettings
from settings_library.rabbit import RabbitSettings
from settings_library.utils_logging import MixinLoggingSettings

from ..modules.resource_tracking.models import ResourceTrackingSettings


class ApplicationSettings(BaseCustomSettings, MixinLoggingSettings):
    SC_BOOT_MODE: BootModeEnum = Field(
        ...,
        description="boot mode helps determine if in development mode or normal operation",
    )

    DYNAMIC_SIDECAR_DY_VOLUMES_MOUNT_DIR: Path = Field(
        ...,
        description="Base directory where dynamic-sidecar stores creates "
        "and shares volumes between itself and the spawned containers. "
        "It is used as a mount directory for the director-v2."
        "Sidecar must have r/w permissions in this folder.",
    )

    DYNAMIC_SIDECAR_SHARED_STORE_DIR: Path = Field(
        ...,
        description="Directory where the dynamic-sidecar persists "
        "it's SharedStore data. This is used in case of reboots of the "
        "container to reload recover the state of the store.",
    )

    # LOGGING
    LOG_LEVEL: str = Field(
        default="WARNING", env=["DYNAMIC_SIDECAR_LOG_LEVEL", "LOG_LEVEL", "LOGLEVEL"]
    )

    # SERVICE SERVER (see : https://www.uvicorn.org/settings/)
    DYNAMIC_SIDECAR_HOST: str = Field(
        default="0.0.0.0",  # nosec
        description="host where to bind the application on which to serve",
    )
    DYNAMIC_SIDECAR_PORT: PortInt = Field(
        default=8000, description="port where the server will be currently serving"
    )

    DYNAMIC_SIDECAR_COMPOSE_NAMESPACE: str = Field(
        ...,
        description=(
            "To avoid collisions when scheduling on the same node, this "
            "will be composed by the project_uuid and node_uuid."
        ),
    )

    DYNAMIC_SIDECAR_MAX_COMBINED_CONTAINER_NAME_LENGTH: PositiveInt = Field(
        default=63, description="the container name which will be used as hostname"
    )

    DYNAMIC_SIDECAR_STOP_AND_REMOVE_TIMEOUT: PositiveInt = Field(
        default=5,
        description=(
            "When receiving SIGTERM the process has 10 seconds to cleanup its children "
            "forcing our children to stop in 5 seconds in all cases"
        ),
    )

    DEBUG: bool = Field(
        default=False,
        description="If set to True the application will boot into debug mode",
    )

    DYNAMIC_SIDECAR_REMOTE_DEBUG_PORT: PortInt = Field(
        default=3000, description="ptsvd remote debugger starting port"
    )

    DY_SIDECAR_PATH_INPUTS: Path = Field(
        ..., description="path where to expect the inputs folder"
    )
    DY_SIDECAR_PATH_OUTPUTS: Path = Field(
        ..., description="path where to expect the outputs folder"
    )
    DY_SIDECAR_STATE_PATHS: list[Path] = Field(
        ..., description="list of additional paths to be synced"
    )
    DY_SIDECAR_STATE_EXCLUDE: set[str] = Field(
        ..., description="list of patterns to exclude files when saving states"
    )
    DY_SIDECAR_LOG_FORMAT_LOCAL_DEV_ENABLED: bool = Field(
        default=False,
        env=["DY_SIDECAR_LOG_FORMAT_LOCAL_DEV_ENABLED", "LOG_FORMAT_LOCAL_DEV_ENABLED"],
        description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
    )
    DY_SIDECAR_USER_ID: UserID
    DY_SIDECAR_PROJECT_ID: ProjectID
    DY_SIDECAR_NODE_ID: NodeID
    DY_SIDECAR_RUN_ID: RunID
    DY_SIDECAR_USER_SERVICES_HAVE_INTERNET_ACCESS: bool

    REGISTRY_SETTINGS: RegistrySettings = Field(auto_default_from_env=True)

    RABBIT_SETTINGS: RabbitSettings | None = Field(auto_default_from_env=True)
    DY_SIDECAR_R_CLONE_SETTINGS: RCloneSettings = Field(auto_default_from_env=True)

    RESOURCE_TRACKING: ResourceTrackingSettings = Field(auto_default_from_env=True)

    @validator("LOG_LEVEL")
    @classmethod
    def _check_log_level(cls, value):
        return cls.validate_log_level(value)


@lru_cache
def get_settings() -> ApplicationSettings:
    """used outside the context of a request"""
    warnings.warn("Use instead app.state.settings", DeprecationWarning, stacklevel=2)
    return cast(ApplicationSettings, ApplicationSettings.create_from_envs())
