"""Reserves resource headroom for helper containers (envoy, otel collector, otel forwarder,
rclone mount) by subtracting their combined footprint from the single biggest user service
in the compose spec before starting it.

Fails sidecar startup if the deduction would leave the target service with:
  - ≤ 0 CPU or ≤ 0 RAM (hard floor), or
  - < DY_SIDECAR_HELPER_CONTAINERS_MIN_REMAINING_RESOURCE_FRACTION of its original CPU or RAM (soft floor).
"""

import logging
import sys
from dataclasses import dataclass
from typing import Any, Final

from fastapi import status
from pydantic import ByteSize
from servicelib.resources import USER_SERVICE_CPU_RESOURCE_LIMIT_ENV_KEY, USER_SERVICE_MEM_RESOURCE_LIMIT_ENV_KEY

from .errors import BaseDynamicSidecarError
from .settings import ApplicationSettings

_logger = logging.getLogger(__name__)
_EPS: Final[float] = sys.float_info.epsilon  # guard against division by zero

# ----- errors ----------------------------------------------------------------


class HelperContainerResourceError(BaseDynamicSidecarError):
    """Base for all extra-container resource allocation failures."""

    status_code: int = status.HTTP_422_UNPROCESSABLE_ENTITY


class NoUserServiceFoundError(HelperContainerResourceError):
    msg_template = (
        "No user service found in the compose spec "
        "(expected at least one service with {cpu_limit_key} in its environment). "
        "Cannot allocate extra-container resources."
    )


class NotEnoughResourcesForHelperContainersError(HelperContainerResourceError):
    msg_template = (
        "Service '{service_name}' cannot fit the helper containers ({helpers_desc}): "
        "remaining cpu: {remaining_cpu:.1f} of {original_cpu:.1f} cores ({remaining_cpu_pct:.0%}); "
        "remaining ram: {remaining_ram_hr} of {original_ram_hr} ({remaining_ram_pct:.0%}). "
        "Remaining must each be > 0 and >= {min_fraction:.0%} of the original. "
        "Increase the service resource allocation."
    )


# ----- resource dataclass ----------------------------------------------------


@dataclass(frozen=True)
class _Resources:
    cpu: float  # cores (e.g. 0.5 = half a core)
    ram: int  # bytes


# ----- compose-spec helpers --------------------------------------------------


def _read_limits(service_spec: dict[str, Any]) -> _Resources:
    """Reads cpu (cores) and ram (bytes) from a compose service spec.

    Handles both:
    - compose v3+: ``deploy.resources.limits.{cpus, memory}``
    - compose v2:  top-level ``cpus`` (float) and ``mem_limit`` (str/int)
    """
    v3_limits = service_spec.get("deploy", {}).get("resources", {}).get("limits", {})
    if v3_limits:
        return _Resources(cpu=float(v3_limits.get("cpus", 0.0)), ram=int(v3_limits.get("memory", 0)))
    # compose v2 stores limits as direct service-level fields
    return _Resources(cpu=float(service_spec.get("cpus", 0.0)), ram=int(service_spec.get("mem_limit", 0)))


def _write_limits(service_spec: dict[str, Any], resources: _Resources) -> None:
    """Writes cpu and ram back into the compose service spec and clamps reservations.

    Detects compose version from the existing spec structure:
    - compose v3+: ``deploy.resources.limits.{cpus, memory}``
    - compose v2:  top-level ``cpus`` and ``mem_limit``

    Also updates ``SIMCORE_NANO_CPUS_LIMIT`` and ``SIMCORE_MEMORY_BYTES_LIMIT`` in the
    service environment so that the user service sees the *reduced* limits that Docker
    will actually enforce — not the original pre-deduction values injected by director-v2.
    """
    if service_spec.get("deploy", {}).get("resources", {}).get("limits"):
        # compose v3+
        limits = service_spec["deploy"]["resources"]["limits"]
        limits["cpus"] = f"{resources.cpu}"
        limits["memory"] = f"{resources.ram}"
        reservations = service_spec["deploy"]["resources"].get("reservations", {})
        if "cpus" in reservations:
            reservations["cpus"] = f"{min(float(reservations['cpus']), resources.cpu)}"
        if "memory" in reservations:
            reservations["memory"] = f"{min(int(reservations['memory']), resources.ram)}"
    else:
        # compose v2
        service_spec["cpus"] = resources.cpu
        service_spec["mem_limit"] = f"{resources.ram}"
        if "mem_reservation" in service_spec:
            service_spec["mem_reservation"] = f"{min(int(service_spec['mem_reservation']), resources.ram)}"

    # Sync the resource-limit env vars that director-v2 already injected.
    # They must reflect the post-deduction limits so the user service is not misled.
    updated_env = {
        USER_SERVICE_CPU_RESOURCE_LIMIT_ENV_KEY: f"{int(resources.cpu * 10**9)}",
        USER_SERVICE_MEM_RESOURCE_LIMIT_ENV_KEY: f"{resources.ram}",
    }

    environment = service_spec.get("environment")
    if environment is None:
        service_spec["environment"] = [f"{k}={v}" for k, v in updated_env.items()]
    elif isinstance(environment, dict):
        environment.update(updated_env)
    else:
        assert isinstance(environment, list)  # nosec
        environment = [e for e in environment if not any(str(e).startswith(f"{key}=") for key in updated_env)]
        environment.extend(f"{k}={v}" for k, v in updated_env.items())
        service_spec["environment"] = environment


# ----- main API --------------------------------------------------------------


def _find_biggest_overall_service(spec_services: dict[str, Any], candidate_names: list[str]) -> str:
    """Returns the candidate service name with the largest RAM limit; CPU is the tiebreaker."""

    def _score(name: str) -> tuple[int, float]:
        r = _read_limits(spec_services[name])
        return (r.ram, r.cpu)

    return max(candidate_names, key=_score)


def _get_biggest_user_service(
    parsed_compose_spec: dict[str, Any],
) -> tuple[str, _Resources]:
    """Returns (service_name, resources) of the biggest user service.

    Raises:
        NoUserServiceFoundError: if no user services exist in the spec.
    """
    spec_services = parsed_compose_spec.get("services", {})
    user_service_names = [name for name, spec in spec_services.items() if _is_user_service(spec)]
    if not user_service_names:
        raise NoUserServiceFoundError(cpu_limit_key=USER_SERVICE_CPU_RESOURCE_LIMIT_ENV_KEY)

    biggest = _find_biggest_overall_service(spec_services, user_service_names)
    return biggest, _read_limits(spec_services[biggest])


def _compute_helper_containers_footprint(
    settings: ApplicationSettings,
    *,
    egress_proxy_count: int,
    with_tracing: bool,
    with_rclone: bool,
    biggest_service_resources: _Resources,
) -> tuple[_Resources, str]:
    """Sums the resource footprint of only the helper containers that are actually added."""
    cpu: float = 0.0
    ram: int = 0
    parts: list[str] = []

    if egress_proxy_count > 0:
        cpu += egress_proxy_count * settings.DY_SIDECAR_EGRESS_PROXY_SETTINGS.DYNAMIC_SIDECAR_ENVOY_CPU_LIMIT
        ram += egress_proxy_count * int(settings.DY_SIDECAR_EGRESS_PROXY_SETTINGS.DYNAMIC_SIDECAR_ENVOY_MEMORY_LIMIT)
        parts.append(f"envoy x{egress_proxy_count}" if egress_proxy_count > 1 else "envoy")

    if with_tracing:
        t = settings.DYNAMIC_SIDECAR_USER_SERVICES_TRACING_CONFIG
        # collector + forwarder share the same CPU/RAM settings
        cpu += 2 * t.USER_SERVICES_TRACING_COLLECTOR_CPU_LIMIT
        ram += 2 * int(t.USER_SERVICES_TRACING_COLLECTOR_MEMORY_LIMIT)
        parts.append("otel collector+forwarder")

    rclone_cpu: float = 0.0
    rclone_ram: int = 0
    if with_rclone:
        mount_settings = settings.DY_SIDECAR_R_CLONE_SETTINGS.R_CLONE_SIMCORE_SDK_MOUNT_SETTINGS
        rclone_cpu = mount_settings.R_CLONE_SIMCORE_SDK_MOUNT_CONTAINER_NANO_CPUS / 1e9
        rclone_ram = int(mount_settings.R_CLONE_SIMCORE_SDK_MOUNT_CONTAINER_MEMORY_LIMIT)
        max_rclone_fraction = (
            settings.DY_SIDECAR_HELPER_CONTAINERS_RESOURCE_SETTINGS.DY_SIDECAR_RCLONE_MAX_SERVICE_RESOURCE_FRACTION
        )
        rclone_cpu = min(rclone_cpu, biggest_service_resources.cpu * max_rclone_fraction)
        rclone_ram = min(rclone_ram, int(biggest_service_resources.ram * max_rclone_fraction))
        cpu += rclone_cpu
        ram += rclone_ram
        parts.append("rclone")

    helpers_desc = ", ".join(parts)
    return _Resources(cpu=cpu, ram=ram), helpers_desc


def _is_user_service(service_spec: dict[str, Any]) -> bool:
    """Returns True if this service was placed by director-v2 as a user service.

    Director-v2 injects ``SIMCORE_NANO_CPUS_LIMIT`` into every user service environment
    via ``_update_resource_limits_and_reservations``.  Helper containers (envoy, otel
    collector, rclone) never receive this variable, making it an image-agnostic marker
    that requires no hardcoded image names or service-name patterns.
    """
    environment = service_spec.get("environment")
    if isinstance(environment, dict):
        return USER_SERVICE_CPU_RESOURCE_LIMIT_ENV_KEY in environment
    if not environment:
        return False
    assert isinstance(environment, list)  # nosec
    return any(str(e).startswith(f"{USER_SERVICE_CPU_RESOURCE_LIMIT_ENV_KEY}=") for e in environment)


def _deduct_helper_containers_resources(
    settings: ApplicationSettings,
    parsed_compose_spec: dict[str, Any],
    *,
    biggest_service_name: str,
    biggest_service_resources: _Resources,
    helpers_resources: _Resources,
    helpers_desc: str,
) -> None:
    """Subtracts the combined helper-container footprint from ``biggest`` user service.

    Mutates ``parsed_compose_spec`` in-place.

    Raises:
        NotEnoughResourcesForHelperContainersError: if the remaining allocation would be <= 0 or
             < DY_SIDECAR_HELPER_CONTAINERS_MIN_REMAINING_RESOURCE_FRACTION of the service's original CPU or RAM limit
    """
    spec_services = parsed_compose_spec["services"]

    resource_settings = settings.DY_SIDECAR_HELPER_CONTAINERS_RESOURCE_SETTINGS

    remaining = _Resources(
        cpu=biggest_service_resources.cpu - helpers_resources.cpu,
        ram=biggest_service_resources.ram - helpers_resources.ram,
    )

    min_fraction = resource_settings.DY_SIDECAR_HELPER_CONTAINERS_MIN_REMAINING_RESOURCE_FRACTION
    hard_fail = remaining.cpu <= 0 or remaining.ram <= 0
    soft_fail = (
        remaining.cpu < biggest_service_resources.cpu * min_fraction
        or remaining.ram < biggest_service_resources.ram * min_fraction
    )

    if hard_fail or soft_fail:
        raise NotEnoughResourcesForHelperContainersError(
            service_name=biggest_service_name,
            helpers_desc=helpers_desc,
            helpers_cpu=helpers_resources.cpu,
            helpers_cpu_pct=helpers_resources.cpu / (biggest_service_resources.cpu + _EPS),
            helpers_ram=helpers_resources.ram,
            helpers_ram_hr=ByteSize(helpers_resources.ram).human_readable(),
            helpers_ram_pct=helpers_resources.ram / (biggest_service_resources.ram + _EPS),
            remaining_cpu=remaining.cpu,
            remaining_cpu_pct=remaining.cpu / (biggest_service_resources.cpu + _EPS),
            remaining_ram=remaining.ram,
            remaining_ram_hr=ByteSize(max(remaining.ram, 0)).human_readable(),
            remaining_ram_pct=max(remaining.ram, 0) / (biggest_service_resources.ram + _EPS),
            original_cpu=biggest_service_resources.cpu,
            original_ram=biggest_service_resources.ram,
            original_ram_hr=ByteSize(biggest_service_resources.ram).human_readable(),
            min_fraction=min_fraction,
        )

    _write_limits(spec_services[biggest_service_name], remaining)

    _logger.info(
        "Removed reserved resources from service '%s' for helper containers (%s): "
        "cpu removed %.1f of %.1f cores (-%.2f%%), remaining %.1f cores (%.2f%%); "
        "ram removed %s of %s (-%.2f%%), remaining %s (%.2f%%)",
        biggest_service_name,
        helpers_desc,
        helpers_resources.cpu,
        biggest_service_resources.cpu,
        helpers_resources.cpu / (biggest_service_resources.cpu + _EPS) * 100,
        remaining.cpu,
        remaining.cpu / (biggest_service_resources.cpu + _EPS) * 100,
        ByteSize(helpers_resources.ram).human_readable(),
        ByteSize(biggest_service_resources.ram).human_readable(),
        helpers_resources.ram / (biggest_service_resources.ram + _EPS) * 100,
        ByteSize(remaining.ram).human_readable(),
        remaining.ram / (biggest_service_resources.ram + _EPS) * 100,
    )


def remove_helper_containers_resources(
    settings: ApplicationSettings,
    parsed_compose_spec: dict[str, Any],
    *,
    egress_proxy_count: int,
    with_tracing: bool,
    with_rclone: bool,
) -> None:
    """Computes and deducts the helper-container resource footprint from the biggest user service.
    Mutates ``parsed_compose_spec`` in-place.

    Raises:
        NoUserServiceFoundError: if no user services exist in the spec.
        NotEnoughResourcesForHelperContainersError: if the remaining allocation would be
        <= 0 or < a percentage of the service's original CPU or RAM limit.
    """
    name, resources = _get_biggest_user_service(parsed_compose_spec)

    helpers, helpers_desc = _compute_helper_containers_footprint(
        settings,
        egress_proxy_count=egress_proxy_count,
        with_tracing=with_tracing,
        with_rclone=with_rclone,
        biggest_service_resources=resources,
    )
    _deduct_helper_containers_resources(
        settings,
        parsed_compose_spec,
        biggest_service_name=name,
        biggest_service_resources=resources,
        helpers_resources=helpers,
        helpers_desc=helpers_desc,
    )
