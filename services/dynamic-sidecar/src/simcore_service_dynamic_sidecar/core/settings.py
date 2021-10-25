import logging
from typing import Any, Optional

from models_library.basic_types import BootModeEnum, PortInt
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.users import UserID
from pydantic import BaseSettings, Field, PositiveInt, validator
from settings_library.docker_registry import RegistrySettings
from settings_library.rabbit import RabbitSettings


# Remove when merging
# https://github.com/ITISFoundation/osparc-simcore/pull/2509
class ToChangeRabbitSettings(RabbitSettings):
    RABBIT_ENABLED: bool = True


class DynamicSidecarSettings(BaseSettings):
    @classmethod
    def create(cls, **settings_kwargs: Any) -> "DynamicSidecarSettings":
        return cls(
            registry=RegistrySettings(),
            RABBIT_SETTINGS=RabbitSettings(),
            **settings_kwargs,
        )

    boot_mode: Optional[BootModeEnum] = Field(
        ...,
        description="boot mode helps determine if in development mode or normal operation",
        env="SC_BOOT_MODE",
    )

    # LOGGING
    log_level_name: str = Field("DEBUG", env="LOG_LEVEL")

    @validator("log_level_name")
    @classmethod
    def match_logging_level(cls, v: str) -> str:
        try:
            getattr(logging, v.upper())
        except AttributeError as err:
            raise ValueError(f"{v.upper()} is not a valid level") from err
        return v.upper()

    # SERVICE SERVER (see : https://www.uvicorn.org/settings/)
    host: str = Field(
        "0.0.0.0",  # nosec
        description="host where to bind the application on which to serve",
    )
    port: PortInt = Field(
        8000, description="port where the server will be currently serving"
    )

    compose_namespace: str = Field(
        ...,
        description=(
            "To avoid collisions when scheduling on the same node, this "
            "will be compsoed by the project_uuid and node_uuid."
        ),
    )

    max_combined_container_name_length: PositiveInt = Field(
        63, description="the container name which will be used as hostname"
    )

    stop_and_remove_timeout: PositiveInt = Field(
        5,
        description=(
            "When receiving SIGTERM the process has 10 seconds to cleanup its children "
            "forcing our children to stop in 5 seconds in all cases"
        ),
    )

    debug: bool = Field(
        False,
        description="If set to True the application will boot into debug mode",
        env="DEBUG",
    )

    remote_debug_port: PortInt = Field(
        3000, description="ptsvd remote debugger starting port"
    )

    docker_compose_down_timeout: PositiveInt = Field(
        15, description="used during shutdown when containers swapend will be removed"
    )

    registry: RegistrySettings

    RABBIT_SETTINGS: ToChangeRabbitSettings
    USER_ID: UserID = Field(..., env="USER_ID")
    PROJECT_ID: ProjectID = Field(..., env="PROJECT_ID")
    NODE_ID: NodeID = Field(..., env="NODE_ID")

    @property
    def is_development_mode(self) -> bool:
        """If in development mode this will be True"""
        return self.boot_mode is BootModeEnum.DEVELOPMENT

    @property
    def loglevel(self) -> int:
        return int(getattr(logging, self.log_level_name))

    class Config:
        case_sensitive = False
        env_prefix = "DYNAMIC_SIDECAR_"
