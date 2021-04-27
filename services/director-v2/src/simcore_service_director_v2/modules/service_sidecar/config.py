# this is a proxy for the global configuration and will be removed in the future
# making it easy to refactor

from aiohttp.web import Application
from pydantic import BaseSettings, Field, PositiveInt

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
        8000,
        description="port on which the webserver for the dynamic-sidecar is exposed",
    )

    simcore_services_network_name: str = Field(
        None,
        description="network all simcore services are currently present",
        env="SIMCORE_SERVICES_NETWORK_NAME",
    )

    dev_expose_service_sidecar: bool = Field(
        False,
        description="if true exposes all the service sidecars to the host for simpler debugging",
    )

    service_sidecar_api_request_timeout: PositiveInt = Field(
        15,
        description=(
            "the default timeout each request to the dynamic-sidecar API in seconds; as per "
            "design, all requests should answer quite quickly, in theory a few seconds or less"
        ),
    )

    service_sidecar_api_request_docker_compose_pull_timeout: PositiveInt = Field(
        3600,
        description=(
            "when pulling images, before running docker-compose up, there is an 1 hour timeout"
        ),
    )

    service_sidecar_api_request_docker_compose_up_timeout: PositiveInt = Field(
        10,
        description=(
            "when running docker-compose up -d if there are errors in the compose spec it can "
            "happen that the command expects some user input, so this will wait forever. To avoid"
            "this situation we are adding a timeout. note that if a compose-spec lots of containers "
            "the current default may not be enough. Also pleasenote that this value has to be "
            "smaller then service_sidecar_api_request_timeout or the errors may not be consistent"
        ),
    )

    service_sidecar_api_request_docker_compose_down_timeout: PositiveInt = Field(
        15,
        description=(
            "used by the dynamic-sidecar when it's shutting down to cleanup all spawned containers; "
            "if the containers tend to remain in the system increasing this will help with removing "
            "pending containers spawned by the dynamic-sidecar"
        ),
    )

    # Trying to resolve docker registry url
    registry_path: str = Field(
        None, description="url to the docker registry", env="REGISTRY_PATH"
    )
    registry_url: str = Field(
        "", description="url to the docker registry", env="REGISTRY_URL"
    )

    timeout_fetch_service_sidecar_node_id: float = Field(
        60,
        description=(
            "when starting the dynamic-sidecar proxy, the NodeID of the dynamic-sidecar container "
            "is required; If something goes wrong timeout and do not wait forever in a loop"
        ),
    )

    @property
    def resolved_registry_url(self) -> str:
        # This is useful in case of a local registry, where the registry url (path) is relative to the host docker engine
        return self.registry_path or self.registry_url

    @property
    def is_dev_mode(self):
        # TODO: ask SAN how to check this, not sure from what env var to derive it
        return True

    class Config:
        case_sensitive = False
        env_prefix = "DYNAMIC_SIDECAR_"


async def setup_settings(app: Application) -> None:
    app.state.service_sidecar_settings = ServiceSidecarSettings()


def get_settings(app: Application) -> ServiceSidecarSettings:
    return app.state.service_sidecar_settings
