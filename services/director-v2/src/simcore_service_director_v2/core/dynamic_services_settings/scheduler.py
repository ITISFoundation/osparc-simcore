from datetime import timedelta
from typing import Final

from common_library.pydantic_validators import validate_numeric_string_as_timedelta
from models_library.projects_networks import DockerNetworkName
from pydantic import Field, NonNegativeInt, PositiveFloat
from settings_library.base import BaseCustomSettings

_MINUTE: Final[NonNegativeInt] = 60


class DynamicServicesSchedulerSettings(BaseCustomSettings):
    DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED: bool = True

    DIRECTOR_V2_DYNAMIC_SCHEDULER_INTERVAL: timedelta = Field(
        timedelta(seconds=5),
        description="interval at which the scheduler cycle is repeated",
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
        "3.8",
        description="docker-compose spec version used in the compose-specs",
        deprecated=True,
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

    DIRECTOR_V2_DYNAMIC_SCHEDULER_CLOSE_SERVICES_VIA_FRONTEND_WHEN_CREDITS_LIMIT_REACHED: (
        bool
    ) = Field(
        default=True,
        description=(
            "when the message indicating there are no more credits left in a wallet "
            "the director-v2 will shutdown the services via the help of the frontend"
        ),
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

    DYNAMIC_SIDECAR_API_SAVE_RESTORE_STATE_TIMEOUT: timedelta = Field(
        timedelta(hours=1),
        description=(
            "When saving and restoring the state of a dynamic service, depending on the payload "
            "some services take longer or shorter to save and restore. Across the "
            "platform this value is set to 1 hour."
        ),
    )

    DYNAMIC_SIDECAR_API_USER_SERVICES_PULLING_TIMEOUT: PositiveFloat = Field(
        60.0 * _MINUTE,
        description="before starting the user services pull all the images in parallel",
    )

    DYNAMIC_SIDECAR_API_RESTART_CONTAINERS_TIMEOUT: PositiveFloat = Field(
        1.0 * _MINUTE,
        description=(
            "Restarts all started containers. During this operation, no data "
            "stored in the container will be lost as docker compose restart "
            "will not alter the state of the files on the disk nor its environment."
        ),
    )

    DYNAMIC_SIDECAR_WAIT_FOR_CONTAINERS_TO_START: PositiveFloat = Field(
        60.0 * _MINUTE,
        description=(
            "When starting container (`docker compose up`), images might "
            "require pulling before containers are started."
        ),
    )

    DYNAMIC_SIDECAR_WAIT_FOR_SERVICE_TO_STOP: PositiveFloat = Field(
        60.0 * _MINUTE,
        description=(
            "When stopping a service, depending on the amount of data to store, "
            "the operation might be very long. Also all relative created resources: "
            "services, containsers, volumes and networks need to be removed. "
        ),
    )

    DYNAMIC_SIDECAR_PROJECT_NETWORKS_ATTACH_DETACH_S: PositiveFloat = Field(
        3.0 * _MINUTE,
        description=(
            "timeout for attaching/detaching project networks to/from a container"
        ),
    )

    DYNAMIC_SIDECAR_CLIENT_REQUEST_TIMEOUT_S: PositiveFloat = Field(
        1 * _MINUTE,
        description=(
            "Connectivity between director-v2 and a dy-sidecar can be "
            "temporarily disrupted if network between swarm nodes has "
            "issues. To avoid the sidecar being marked as failed, "
            "allow for some time to pass before declaring it failed."
        ),
    )

    #
    # DEBUG
    #

    DIRECTOR_V2_DYNAMIC_SIDECAR_SLEEP_AFTER_CONTAINER_REMOVAL: timedelta = Field(
        timedelta(0), description="time to sleep before removing a container"
    )

    _validate_director_v2_dynamic_scheduler_interval = (
        validate_numeric_string_as_timedelta("DIRECTOR_V2_DYNAMIC_SCHEDULER_INTERVAL")
    )
    _validate_director_v2_dynamic_sidecar_sleep_after_container_removal = (
        validate_numeric_string_as_timedelta(
            "DIRECTOR_V2_DYNAMIC_SIDECAR_SLEEP_AFTER_CONTAINER_REMOVAL"
        )
    )
