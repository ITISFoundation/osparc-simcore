# this is a proxy for the global configuration and will be removed in the future
# making it easy to refactor

from pydantic import BaseSettings, Field
from aiohttp.web import Application


KEY_SERVICE_SIDECAR_SETTINGS = f"{__name__}.ServiceSidecarSettings"


class ServiceSidecarSettings(BaseSettings):
    # service_sidecar integration
    monitor_interval_seconds: float = Field(
        5.0, description="interval at which the monitor cycle is repeated"
    )

    max_status_api_duration: float = Field(
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

    dev_simcore_service_sidecar_path: str = Field(
        None,
        description="optional, only used for development, mounts the source of the service sidecar",
        env="DEV_SIMCORE_SERVICE_SIDECAR_PATH",
    )

    image: str = Field(
        ...,
        description="used by the director to start a specific version of the service sidecar",
    )

    web_service_port: int = Field(
        8000, description="port on which the webserver is exposed"
    )

    simcore_services_network_name: str = Field(
        None,
        description="network all simcore services are currently present",
        env="SIMCORE_SERVICES_NETWORK_NAME",
    )

    @property
    def is_dev_mode(self):
        # TODO: ask SAN how to check this, not sure from what env var to derive it
        return True

    class Config:
        case_sensitive = False
        env_prefix = "SERVICE_SIDECAR_"


async def setup_settings(app: Application) -> None:
    app[KEY_SERVICE_SIDECAR_SETTINGS] = ServiceSidecarSettings()


def get_settings(app: Application) -> ServiceSidecarSettings:
    return app[KEY_SERVICE_SIDECAR_SETTINGS]
