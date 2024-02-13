from pydantic import Field
from settings_library.base import BaseCustomSettings

from .egress_proxy import EgressProxySettings
from .proxy import DynamicSidecarProxySettings
from .scheduler import DynamicServicesSchedulerSettings
from .sidecar import DynamicSidecarSettings, PlacementSettings


class DynamicServicesSettings(BaseCustomSettings):
    DIRECTOR_V2_DYNAMIC_SERVICES_ENABLED: bool = Field(
        default=True, description="Enables/Disables the dynamic_sidecar submodule"
    )

    DYNAMIC_SIDECAR: DynamicSidecarSettings = Field(auto_default_from_env=True)

    DYNAMIC_SCHEDULER: DynamicServicesSchedulerSettings = Field(
        auto_default_from_env=True
    )

    DYNAMIC_SIDECAR_PROXY_SETTINGS: DynamicSidecarProxySettings = Field(
        auto_default_from_env=True
    )

    DYNAMIC_SIDECAR_EGRESS_PROXY_SETTINGS: EgressProxySettings = Field(
        auto_default_from_env=True
    )

    DYNAMIC_SIDECAR_PLACEMENT_SETTINGS: PlacementSettings = Field(
        auto_default_from_env=True
    )
