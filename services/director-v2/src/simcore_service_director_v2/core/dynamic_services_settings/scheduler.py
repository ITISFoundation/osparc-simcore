from typing import Final

from models_library.projects_networks import DockerNetworkName
from pydantic import Field, NonNegativeInt, PositiveFloat
from settings_library.base import BaseCustomSettings

_MINUTE: Final[NonNegativeInt] = 60


class DynamicServicesSchedulerSettings(BaseCustomSettings):
    DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED: bool = True

    DIRECTOR_V2_DYNAMIC_SCHEDULER_INTERVAL_SECONDS: PositiveFloat = Field(
        5.0, description="interval at which the scheduler cycle is repeated"
    )

    DIRECTOR_V2_DYNAMIC_SCHEDULER_PENDING_VOLUME_REMOVAL_INTERVAL_S: PositiveFloat = (
        Field(
            30 * _MINUTE,
            description="interval at which cleaning of unused dy-sidecar "
            "docker volume removal services is executed",
        )
    )

    SIMCORE_SERVICES_NETWORK_NAME: DockerNetworkName = Field(
        ...,
        description="network all dynamic services are connected to",
    )

    DYNAMIC_SIDECAR_DOCKER_COMPOSE_VERSION: str = Field(
        "3.8", description="docker-compose spec version used in the compose-specs"
    )

    DYNAMIC_SIDECAR_ENABLE_VOLUME_LIMITS: bool = Field(
        default=False,
        description="enables support for limiting service's volume size",
    )

    SWARM_STACK_NAME: str = Field(
        ...,
        description="in case there are several deployments on the same docker swarm, it is attached as a label on all spawned services",
    )

    TRAEFIK_SIMCORE_ZONE: str = Field(
        ...,
        description="Names the traefik zone for services that must be accessible from platform http entrypoint",
    )

    DYNAMIC_SIDECAR_PROMETHEUS_SERVICE_LABELS: dict[str, str] = Field(
        ...,
        description=(
            "Provided by ops, are injected as service labels when starting the dy-sidecar, "
            "and Prometheus identifies the service as to be scraped"
        ),
    )

    DYNAMIC_SIDECAR_PROMETHEUS_MONITORING_NETWORKS: list[str] = Field(
        default_factory=list,
        description="Prometheus will scrape service placed on these networks",
    )

    #
    # TIMEOUTS AND RETRY dark worlds
    #
    DYNAMIC_SIDECAR_API_REQUEST_TIMEOUT: PositiveFloat = Field(
        15.0,
        description=(
            "the default timeout each request to the dynamic-sidecar API in seconds; as per "
            "design, all requests should answer quite quickly, in theory a few seconds or less"
        ),
    )

    DYNAMIC_SIDECAR_API_CONNECT_TIMEOUT: PositiveFloat = Field(
        5.0,
        description=(
            "Connections to the dynamic-sidecars in the same swarm deployment should be very fast."
        ),
    )

    DYNAMIC_SIDECAR_STARTUP_TIMEOUT_S: PositiveFloat = Field(
        60 * _MINUTE,
        description=(
            "After starting the dynamic-sidecar its docker_node_id is required. "
            "This operation can be slow based on system load, sometimes docker "
            "swarm takes more than seconds to assign the node."
            "Autoscaling of nodes takes time, it is required to wait longer"
            "for nodes to be assigned."
        ),
    )

    DYNAMIC_SIDECAR_API_SAVE_RESTORE_STATE_TIMEOUT: PositiveFloat = Field(
        60.0 * _MINUTE,
        description=(
            "When saving and restoring the state of a dynamic service, depending on the payload "
            "some services take longer or shorter to save and restore. Across the "
            "platform this value is set to 1 hour."
        ),
    )
