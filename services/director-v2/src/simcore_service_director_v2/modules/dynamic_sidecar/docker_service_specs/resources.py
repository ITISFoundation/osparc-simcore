"""Resource arithmetic for the containers the dynamic-sidecar hosts.

Kept free of docker/catalog dependencies so it can be tested in isolation.
"""

from models_library.services_resources import (
    GIGA,
    SIDECAR_HELPERS_RESOURCE_KEY,
    ServiceResourcesDict,
)
from pydantic import ByteSize, TypeAdapter
from settings_library.r_clone import RCloneSimcoreSDKMountSettings

from ....core.dynamic_services_settings import DynamicServicesSettings


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
        cpu += mount_settings.R_CLONE_SIMCORE_SDK_MOUNT_CONTAINER_NANO_CPUS / GIGA
        ram += int(get_max_rclone_container_memory_limit(mount_settings, max_user_service_container_memory))

    return cpu, ram
