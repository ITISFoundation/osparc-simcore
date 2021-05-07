# this is a proxy for the global configuration and will be removed in the future
# making it easy to refactor

from pathlib import Path
from typing import Optional
from aiohttp.web import Application
from pydantic import BaseSettings, Field, PositiveInt, PositiveFloat
from models_library.basic_types import PortInt, BootModeEnum
from models_library.services import SERVICE_KEY_RE


class DynamicSidecarSettings(BaseSettings):
    # dynamic_sidecar integration
    monitor_interval_seconds: PositiveFloat = Field(
        5.0, description="interval at which the monitor cycle is repeated"
    )

    max_status_api_duration: PositiveFloat = Field(
        1.0,
        description=(
            "when requesting the status of a service this is the "
            "maximum amount of time the request can last"
        ),
    )

    traefik_simcore_zone: str = Field(
        "internal_simcore_stack",
        description="used by Traefik to properly handle forwarding of requests",
        env="TRAEFIK_SIMCORE_ZONE",
    )

    swarm_stack_name: str = Field(
        "undefined-please-check",
        description="used to filter out docker components from other deployments running on same swarm",
        env="SWARM_STACK_NAME",
    )

    dev_simcore_dynamic_sidecar_path: Path = Field(
        None,
        description="optional, only used for development, mounts the source of the dynamic-sidecar",
        env="DEV_SIMCORE_DYNAMIC_SIDECAR_PATH",
    )

    image: str = Field(
        ...,
        regex=SERVICE_KEY_RE,
        description="used by the director to start a specific version of the dynamic-sidecar",
    )

    web_service_port: PortInt = Field(
        8000,
        description="port on which the webserver for the dynamic-sidecar is exposed",
    )

    simcore_services_network_name: Optional[str] = Field(
        None,
        regex=r"^([a-zA-Z0-9_]+)$",
        description="network all simcore services are currently present",
        env="SIMCORE_SERVICES_NETWORK_NAME",
    )

    dev_expose_dynamic_sidecar: bool = Field(
        False,
        description="if true exposes all the dynamic-sidecars to the host for simpler debugging",
    )

    dynamic_sidecar_api_request_timeout: PositiveInt = Field(
        15,
        description=(
            "the default timeout each request to the dynamic-sidecar API in seconds; as per "
            "design, all requests should answer quite quickly, in theory a few seconds or less"
        ),
    )

    # Trying to resolve docker registry url
    registry_path: Optional[str] = Field(
        None, description="url to the docker registry", env="REGISTRY_PATH"
    )
    registry_url: str = Field(
        "", description="url to the docker registry", env="REGISTRY_URL"
    )

    timeout_fetch_dynamic_sidecar_node_id: PositiveFloat = Field(
        60,
        description=(
            "when starting the dynamic-sidecar proxy, the NodeID of the dynamic-sidecar container "
            "is required; If something goes wrong timeout and do not wait forever in a loop"
        ),
    )

    boot_mode: Optional[BootModeEnum] = Field(
        BootModeEnum.PRODUCTION,
        description="Used to compute where or not should start sidecar in development mode",
        env="SC_BOOT_MODE",
    )

    @property
    def resolved_registry_url(self) -> str:
        # This is useful in case of a local registry, where the registry url (path) is relative to the host docker engine
        return self.registry_path or self.registry_url

    @property
    def is_dev_mode(self) -> bool:
        return self.boot_mode in {
            BootModeEnum.DEVELOPMENT,
            BootModeEnum.DEBUG,
            BootModeEnum.LOCAL,
        }

    class Config:
        case_sensitive = False
        env_prefix = "DYNAMIC_SIDECAR_"


async def setup_settings(app: Application) -> None:
    app.state.dynamic_sidecar_settings = DynamicSidecarSettings()


def get_settings(app: Application) -> DynamicSidecarSettings:
    return app.state.dynamic_sidecar_settings
