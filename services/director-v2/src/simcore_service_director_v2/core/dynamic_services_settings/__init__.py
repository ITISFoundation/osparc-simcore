from pydantic import Field
from settings_library.base import BaseCustomSettings

from .scheduler import DynamicServicesSchedulerSettings
from .sidecar import DynamicSidecarSettings


class DynamicServicesSettings(BaseCustomSettings):
    DIRECTOR_V2_DYNAMIC_SERVICES_ENABLED: bool = Field(
        default=True, description="Enables/Disables the dynamic_sidecar submodule"
    )

    DYNAMIC_SIDECAR: DynamicSidecarSettings = Field(auto_default_from_env=True)

    DYNAMIC_SCHEDULER: DynamicServicesSchedulerSettings = Field(
        auto_default_from_env=True
    )
