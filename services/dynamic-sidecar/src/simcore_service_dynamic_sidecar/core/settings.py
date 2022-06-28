import warnings
from functools import lru_cache
from pathlib import Path
from typing import Optional, cast
from uuid import UUID

from models_library.basic_types import BootModeEnum, PortInt
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.users import UserID
from pydantic import Field, PositiveInt, validator
from settings_library.base import BaseCustomSettings
from settings_library.docker_registry import RegistrySettings
from settings_library.r_clone import RCloneSettings
from settings_library.rabbit import RabbitSettings
from settings_library.utils_logging import MixinLoggingSettings


class DynamicSidecarSettings(BaseCustomSettings, MixinLoggingSettings):

    SC_BOOT_MODE: Optional[BootModeEnum] = Field(
        ...,
        description="boot mode helps determine if in development mode or normal operation",
    )

    # LOGGING
    LOG_LEVEL: str = Field("WARNING")

    # SERVICE SERVER (see : https://www.uvicorn.org/settings/)
    DYNAMIC_SIDECAR_HOST: str = Field(
        "0.0.0.0",  # nosec
        description="host where to bind the application on which to serve",
    )
    DYNAMIC_SIDECAR_PORT: PortInt = Field(
        8000, description="port where the server will be currently serving"
    )

    DYNAMIC_SIDECAR_COMPOSE_NAMESPACE: str = Field(
        ...,
        description=(
            "To avoid collisions when scheduling on the same node, this "
            "will be compsoed by the project_uuid and node_uuid."
        ),
    )

    DYNAMIC_SIDECAR_MAX_COMBINED_CONTAINER_NAME_LENGTH: PositiveInt = Field(
        63, description="the container name which will be used as hostname"
    )

    DYNAMIC_SIDECAR_STOP_AND_REMOVE_TIMEOUT: PositiveInt = Field(
        5,
        description=(
            "When receiving SIGTERM the process has 10 seconds to cleanup its children "
            "forcing our children to stop in 5 seconds in all cases"
        ),
    )

    DEBUG: bool = Field(
        False,
        description="If set to True the application will boot into debug mode",
    )

    DYNAMIC_SIDECAR_REMOTE_DEBUG_PORT: PortInt = Field(
        3000, description="ptsvd remote debugger starting port"
    )

    DYNAMIC_SIDECAR_DOCKER_COMPOSE_DOWN_TIMEOUT: PositiveInt = Field(
        15, description="used during shutdown when containers swapend will be removed"
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
    DY_SIDECAR_STATE_EXCLUDE: list[str] = Field(
        ..., description="list of patterns to exclude files when saving states"
    )
    DY_SIDECAR_USER_ID: UserID
    DY_SIDECAR_PROJECT_ID: ProjectID
    DY_SIDECAR_NODE_ID: NodeID
    DY_SIDECAR_RUN_ID: UUID

    REGISTRY_SETTINGS: RegistrySettings = Field(auto_default_from_env=True)

    RABBIT_SETTINGS: Optional[RabbitSettings] = Field(auto_default_from_env=True)
    DY_SIDECAR_R_CLONE_SETTINGS: RCloneSettings = Field(auto_default_from_env=True)

    @validator("LOG_LEVEL")
    @classmethod
    def _check_log_level(cls, value) -> str:
        return cls.validate_log_level(value)

    @property
    def is_development_mode(self) -> bool:
        """If in development mode this will be True"""
        return self.SC_BOOT_MODE is BootModeEnum.DEVELOPMENT

    @property
    def rclone_settings_for_nodeports(self) -> Optional[RCloneSettings]:
        """
        If R_CLONE_ENABLED is False it returns None which indicates
        nodeports to disable rclone and fallback to the previous storage mechanim.
        """
        return (
            self.DY_SIDECAR_R_CLONE_SETTINGS
            if self.DY_SIDECAR_R_CLONE_SETTINGS.R_CLONE_ENABLED
            else None
        )


@lru_cache
def get_settings() -> DynamicSidecarSettings:
    """used outside the context of a request"""
    warnings.warn(
        "Use instead app.state.settings",
        DeprecationWarning,
    )
    return cast(DynamicSidecarSettings, DynamicSidecarSettings.create_from_envs())
