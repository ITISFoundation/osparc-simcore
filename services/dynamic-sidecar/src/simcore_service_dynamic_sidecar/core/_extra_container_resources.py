"""Reserves resource headroom for helper containers (envoy, otel collector, otel forwarder,
rclone mount) by subtracting their combined footprint from the single biggest user service
in the compose spec before starting it.

Fails sidecar startup if the deduction would leave the target service with:
  - ≤ 0 CPU or ≤ 0 RAM (hard floor), or
  - < DY_SIDECAR_EXTRA_CONTAINERS_MIN_REMAINING_RESOURCE_FRACTION of its original CPU or RAM (soft floor).
"""

from dataclasses import dataclass
from typing import Any

from pydantic import ByteSize
from servicelib.resources import CPU_RESOURCE_LIMIT_KEY, MEM_RESOURCE_LIMIT_KEY

from .errors import BaseDynamicSidecarError
from .settings import ApplicationSettings

# ----- errors ----------------------------------------------------------------


class ExtraContainerResourceError(BaseDynamicSidecarError):
    """Base for all extra-container resource allocation failures."""


class NotEnoughResourcesForExtraContainersError(ExtraContainerResourceError):
    msg_template = (
        "Service '{service_name}' cannot fit the extra helper containers ({helpers_desc}): "
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
    description: str = ""  # human-readable list of included helper containers


# ----- compose-spec helpers --------------------------------------------------


def _read_limits(service_spec: dict[str, Any]) -> _Resources:
    """Reads cpu (cores) and ram (bytes) from a compose service spec.

    Handles both:
    - compose v3+: ``deploy.resources.limits.{cpus, memory}``
    - compose v2:  top-level ``cpus`` (float) and ``mem_limit`` (str/int)
    """
    v3_limits = service_spec.get("deploy", {}).get("resources", {}).get("limits", {})
    if v3_limits:
        return _Resources(
            cpu=float(v3_limits.get("cpus", 0.0)),
            ram=int(v3_limits.get("memory", 0)),
        )
    # compose v2 stores limits as direct service-level fields
    return _Resources(
        cpu=float(service_spec.get("cpus", 0.0)),
        ram=int(service_spec.get("mem_limit", 0)),
    )


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
        CPU_RESOURCE_LIMIT_KEY: f"{int(resources.cpu * 10**9)}",
        MEM_RESOURCE_LIMIT_KEY: f"{resources.ram}",
    }
    environment: list[str] = service_spec.get("environment", [])
    environment = [e for e in environment if all(key not in e for key in updated_env)]
    environment.extend(f"{k}={v}" for k, v in updated_env.items())
    service_spec["environment"] = environment


# ----- main API --------------------------------------------------------------


def _find_biggest_overall_service(spec_services: dict[str, Any], candidate_names: list[str]) -> str:
    """Returns the candidate service name with the largest RAM limit; CPU is the tiebreaker."""

    def _score(name: str) -> tuple[int, float]:
        r = _read_limits(spec_services[name])
        return (r.ram, r.cpu)

    return max(candidate_names, key=_score)


def compute_extra_containers_footprint(
    settings: ApplicationSettings,
    *,
    egress_proxy_count: int,
    with_tracing: bool,
    with_rclone: bool,
) -> _Resources:
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

    if with_rclone:
        m = settings.DY_SIDECAR_R_CLONE_SETTINGS.R_CLONE_SIMCORE_SDK_MOUNT_SETTINGS
        cpu += m.R_CLONE_SIMCORE_SDK_MOUNT_CONTAINER_NANO_CPUS / 1e9
        ram += int(m.R_CLONE_SIMCORE_SDK_MOUNT_CONTAINER_MEMORY_LIMIT)
        parts.append("rclone")

    return _Resources(cpu=cpu, ram=ram, description=", ".join(parts))


def _is_user_service(service_spec: dict[str, Any]) -> bool:
    """Returns True if this service was placed by director-v2 as a user service.

    Director-v2 injects ``SIMCORE_NANO_CPUS_LIMIT`` into every user service environment
    via ``_update_resource_limits_and_reservations``.  Helper containers (envoy, otel
    collector, rclone) never receive this variable, making it an image-agnostic marker
    that requires no hardcoded image names or service-name patterns.
    """
    environment: list[str] = service_spec.get("environment", [])
    return any(e.startswith(f"{CPU_RESOURCE_LIMIT_KEY}=") for e in environment)


def deduct_extra_containers_resources(
    parsed_compose_spec: dict[str, Any],
    *,
    extra: _Resources,
    settings: ApplicationSettings,
) -> None:
    """Subtracts the combined helper-container footprint from the single biggest user service.

    Identifies user services by the presence of ``SIMCORE_NANO_CPUS_LIMIT`` in their
    environment (injected by director-v2) — no image names or service-name patterns needed.

    Mutates ``parsed_compose_spec`` in-place.

    Raises:
        NotEnoughResourcesForExtraContainersError: if the remaining allocation would be <= 0 or
            < DY_SIDECAR_EXTRA_CONTAINERS_MIN_REMAINING_RESOURCE_FRACTION of the service's original CPU or RAM limit
    """
    spec_services = parsed_compose_spec["services"]
    user_service_names = [name for name, spec in spec_services.items() if _is_user_service(spec)]
    if not user_service_names:
        return

    spec_services = parsed_compose_spec["services"]
    biggest = _find_biggest_overall_service(spec_services, user_service_names)
    original = _read_limits(spec_services[biggest])

    remaining = _Resources(cpu=original.cpu - extra.cpu, ram=original.ram - extra.ram)

    min_fraction = settings.DY_SIDECAR_EXTRA_CONTAINERS_MIN_REMAINING_RESOURCE_FRACTION
    hard_fail = remaining.cpu <= 0 or remaining.ram <= 0
    soft_fail = remaining.cpu < original.cpu * min_fraction or remaining.ram < original.ram * min_fraction

    if hard_fail or soft_fail:
        raise NotEnoughResourcesForExtraContainersError(
            service_name=biggest,
            helpers_desc=extra.description,
            extra_cpu=extra.cpu,
            extra_cpu_pct=extra.cpu / original.cpu if original.cpu else 0.0,
            extra_ram=extra.ram,
            extra_ram_hr=ByteSize(extra.ram).human_readable(),
            extra_ram_pct=extra.ram / original.ram if original.ram else 0.0,
            remaining_cpu=remaining.cpu,
            remaining_cpu_pct=remaining.cpu / original.cpu if original.cpu else 0.0,
            remaining_ram=remaining.ram,
            remaining_ram_hr=ByteSize(max(remaining.ram, 0)).human_readable(),
            remaining_ram_pct=max(remaining.ram, 0) / original.ram if original.ram else 0.0,
            original_cpu=original.cpu,
            original_ram=original.ram,
            original_ram_hr=ByteSize(original.ram).human_readable(),
            min_fraction=min_fraction,
        )

    _write_limits(spec_services[biggest], remaining)
