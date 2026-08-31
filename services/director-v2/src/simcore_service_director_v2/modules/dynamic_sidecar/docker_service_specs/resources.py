"""Resource arithmetic for the containers the dynamic-sidecar hosts.

Kept free of docker/catalog dependencies so it can be tested in isolation.
"""

from collections import Counter
from dataclasses import dataclass
from typing import Final

from models_library.services_resources import (
    DEFAULT_SINGLE_SERVICE_NAME,
    SIDECAR_HELPERS_RESOURCE_KEY,
    ImageResources,
    ResourceValue,
    ServiceResourcesDict,
)
from pydantic import ByteSize, TypeAdapter
from servicelib.docker_utils import (
    DYNAMIC_SIDECAR_MIN_CPUS,
    estimate_dynamic_sidecar_resources_from_ec2_instance,
)
from settings_library.r_clone import RCloneSimcoreSDKMountSettings

from ....core.dynamic_services_settings import DynamicServicesSettings

# below these the user service cannot realistically run
_MIN_USER_SERVICE_CPUS: Final[float] = 1.0
_MIN_USER_SERVICE_RAM: Final[ByteSize] = TypeAdapter(ByteSize).validate_python("1GiB")
_MIN_SUB_SERVICE_RAM: Final[ByteSize] = TypeAdapter(ByteSize).validate_python("128MiB")


@dataclass(frozen=True)
class NotEnoughInstanceResourcesError(Exception):
    cpus: float
    ram: int


@dataclass(frozen=True)
class MissingResourceKeysError(Exception):
    container_name: str
    missing_key: str


def _get_resource(image_resources: ImageResources, key: str, *, container_name: str) -> ResourceValue:
    try:
        return image_resources.resources[key]
    except KeyError as exc:
        raise MissingResourceKeysError(container_name=container_name, missing_key=key) from exc


def get_max_user_service_container_memory(service_resources: ServiceResourcesDict) -> ByteSize:
    """largest RAM limit declared among the user-service containers (excludes the synthetic helper-containers entry)"""
    user_service_ram_limits = [
        int(image_resources.resources["RAM"].limit)
        for key, image_resources in service_resources.items()
        if key != SIDECAR_HELPERS_RESOURCE_KEY and "RAM" in image_resources.resources
    ]
    return TypeAdapter(ByteSize).validate_python(max(user_service_ram_limits, default=0))


def get_max_rclone_container_memory_limit(
    mount_settings: RCloneSimcoreSDKMountSettings, max_user_service_container_memory: ByteSize
) -> ByteSize:
    """
    returns a clapped value between max and min limits
    max is a percentage of the max_user_service_container_memory value
    """
    max_user_service_limit = int(
        max_user_service_container_memory
        * mount_settings.R_CLONE_SIMCORE_SDK_MOUNT_CONTAINER_MEMORY_PERCENT_OF_MAX_USER_SERVICE
    )
    clamped = min(
        max(mount_settings.R_CLONE_SIMCORE_SDK_MOUNT_CONTAINER_MEMORY_LIMIT_MIN, max_user_service_limit),
        mount_settings.R_CLONE_SIMCORE_SDK_MOUNT_CONTAINER_MEMORY_LIMIT_MAX,
    )
    return TypeAdapter(ByteSize).validate_python(clamped)


def compute_helper_containers_resources(
    *,
    dynamic_services_settings: DynamicServicesSettings,
    egress_proxy_count: int,
    with_tracing: bool,
    with_rclone: bool,
    max_user_service_container_memory: ByteSize,
) -> tuple[float, int]:
    """Combined CPU/RAM footprint of the egress-proxy, tracing and rclone helper
    containers that the dynamic-sidecar creates but which are NOT their own Swarm
    services (dy-proxy/caddy is excluded: it already runs as its own Swarm service).
    Single source of truth reused both when director-v2 ADDS this overhead to the
    dynamic-sidecar's own resources, and when it is queried (e.g. by the webserver,
    via RPC) to be SUBTRACTED in advance from the main service's resources.
    """
    cpu = 0.0
    ram = 0

    egress_proxy_settings = dynamic_services_settings.DYNAMIC_SIDECAR_EGRESS_PROXY_SETTINGS
    cpu += egress_proxy_count * egress_proxy_settings.DYNAMIC_SIDECAR_ENVOY_CPU_LIMIT.cores
    ram += egress_proxy_count * int(egress_proxy_settings.DYNAMIC_SIDECAR_ENVOY_MEMORY_LIMIT)

    if with_tracing:
        tracing_settings = dynamic_services_settings.DYNAMIC_SIDECAR_USER_SERVICES_TRACING_CONFIG
        # otel collector (injected in compose) + otel forwarder (created via docker API)
        cpu += 2 * tracing_settings.USER_SERVICES_TRACING_COLLECTOR_CPU_LIMIT.cores
        ram += 2 * int(tracing_settings.USER_SERVICES_TRACING_COLLECTOR_MEMORY_LIMIT)

    if with_rclone:
        r_clone_settings = dynamic_services_settings.DYNAMIC_SIDECAR.DYNAMIC_SIDECAR_R_CLONE_SETTINGS
        mount_settings = r_clone_settings.R_CLONE_SIMCORE_SDK_MOUNT_SETTINGS
        cpu += mount_settings.R_CLONE_SIMCORE_SDK_MOUNT_CONTAINER_CPU_LIMIT.cores
        ram += int(get_max_rclone_container_memory_limit(mount_settings, max_user_service_container_memory))

    return cpu, ram


def scale_service_resources_to_instance_type(
    service_resources: ServiceResourcesDict,
    *,
    dynamic_services_settings: DynamicServicesSettings,
    egress_proxy_count: int,
    with_tracing: bool,
    with_rclone: bool,
    instance_cpus: float,
    instance_ram: ByteSize,
) -> ServiceResourcesDict:
    """Rescales `service_resources` so the whole node (user services + dynamic-sidecar +
    its helper containers) fits the given machine.

    Raises `NotEnoughInstanceResourcesError` when what is left for the user service is
    below the minimum needed to run it.
    """
    available_cpus, available_ram = estimate_dynamic_sidecar_resources_from_ec2_instance(instance_cpus, instance_ram)

    scalable_service_name = DEFAULT_SINGLE_SERVICE_NAME
    if DEFAULT_SINGLE_SERVICE_NAME not in service_resources:
        # scale the most memory-hungry sub-service and leave the others untouched
        scalable_service_name, _ = max(
            service_resources.items(),
            key=lambda name_to_resources: int(
                _get_resource(name_to_resources[1], "RAM", container_name=name_to_resources[0]).limit
            ),
        )
        other_services = Counter({"RAM": 0, "CPU": 0})
        for service_name, sub_service_resources in service_resources.items():
            if service_name != scalable_service_name:
                other_services.update(
                    {
                        "RAM": _get_resource(sub_service_resources, "RAM", container_name=service_name).limit,
                        "CPU": _get_resource(sub_service_resources, "CPU", container_name=service_name).limit,
                    }
                )
        available_cpus = max(available_cpus - other_services["CPU"], DYNAMIC_SIDECAR_MIN_CPUS)
        available_ram = int(max(available_ram - other_services["RAM"], _MIN_SUB_SERVICE_RAM))

    helpers_cpus, helpers_ram = compute_helper_containers_resources(
        dynamic_services_settings=dynamic_services_settings,
        egress_proxy_count=egress_proxy_count,
        with_tracing=with_tracing,
        with_rclone=with_rclone,
        max_user_service_container_memory=TypeAdapter(ByteSize).validate_python(available_ram),
    )
    sidecar_settings = dynamic_services_settings.DYNAMIC_SIDECAR
    available_cpus -= helpers_cpus + sidecar_settings.DYNAMIC_SIDECAR_OWN_CPU_LIMIT.cores
    available_ram = int(available_ram - helpers_ram - int(sidecar_settings.DYNAMIC_SIDECAR_OWN_MEMORY_LIMIT))

    if available_cpus < _MIN_USER_SERVICE_CPUS or available_ram < _MIN_USER_SERVICE_RAM:
        raise NotEnoughInstanceResourcesError(cpus=available_cpus, ram=available_ram)

    scalable = service_resources[scalable_service_name]
    _get_resource(scalable, "CPU", container_name=scalable_service_name).set_value(available_cpus)
    _get_resource(scalable, "RAM", container_name=scalable_service_name).set_value(available_ram)
    return service_resources
