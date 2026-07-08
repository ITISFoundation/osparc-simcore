"""Reserves resource headroom for helper containers (envoy, otel collector, otel forwarder,
rclone mount) by subtracting their combined footprint from the single biggest user service
in the compose spec before starting it.

Fails sidecar startup if the deduction would leave the target service with:
  - ≤ 0 CPU or ≤ 0 RAM (hard floor), or
  - < 48 % of its original CPU or RAM (soft floor).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from servicelib.resources import CPU_RESOURCE_LIMIT_KEY, MEM_RESOURCE_LIMIT_KEY

from .errors import BaseDynamicSidecarError

if TYPE_CHECKING:
    from .settings import ApplicationSettings


# A service must retain at least this fraction of its *own* original allocation
# after all helper footprints are subtracted.
_MIN_REMAINING_FRACTION: Final[float] = 0.48


# ----- errors ----------------------------------------------------------------


class ExtraContainerResourceError(BaseDynamicSidecarError):
    """Base for all extra-container resource allocation failures."""


class NotEnoughResourcesForExtraContainersError(ExtraContainerResourceError):
    msg_template = (
        "Service '{service_name}' has insufficient resource allocation to accommodate "
        "the extra helper containers (envoy/otel/rclone). "
        "After reserving cpu={extra_cpu:.3f} cores and ram={extra_ram} bytes for helpers, "
        "the service would be left with cpu={remaining_cpu:.3f} cores and ram={remaining_ram} bytes "
        "(original: cpu={original_cpu:.3f} cores, ram={original_ram} bytes). "
        "Both cpu and ram remaining must be > 0 and >= {min_fraction:.0%} of the original. "
        "Increase the service resource allocation in the osparc platform."
    )


# ----- resource dataclass ----------------------------------------------------


@dataclass(frozen=True)
class _Resources:
    cpu: float  # cores (e.g. 0.5 = half a core)
    ram: int  # bytes


# ----- compose-spec helpers --------------------------------------------------


def _read_limits(service_spec: dict[str, Any]) -> _Resources:
    """Reads cpu (cores) and ram (bytes) from ``deploy.resources.limits``."""
    limits = service_spec.get("deploy", {}).get("resources", {}).get("limits", {})
    return _Resources(
        cpu=float(limits.get("cpus", 0.0)),
        ram=int(limits.get("memory", 0)),
    )


def _write_limits(service_spec: dict[str, Any], resources: _Resources) -> None:
    """Writes cpu and ram back into ``deploy.resources.limits`` and clamps reservations.

    Also updates ``SIMCORE_NANO_CPUS_LIMIT`` and ``SIMCORE_MEMORY_BYTES_LIMIT`` in the
    service environment so that the user service sees the *reduced* limits that Docker
    will actually enforce — not the original pre-deduction values injected by director-v2.
    """
    deploy = service_spec.setdefault("deploy", {})
    res = deploy.setdefault("resources", {})
    limits = res.setdefault("limits", {})
    limits["cpus"] = f"{resources.cpu}"
    limits["memory"] = f"{resources.ram}"

    # keep reservations <= new limits (Docker/compose requirement)
    reservations = res.get("reservations", {})
    if "cpus" in reservations:
        reservations["cpus"] = f"{min(float(reservations['cpus']), resources.cpu)}"
    if "memory" in reservations:
        reservations["memory"] = f"{min(int(reservations['memory']), resources.ram)}"

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

    if egress_proxy_count > 0:
        cpu += egress_proxy_count * settings.DY_SIDECAR_EGRESS_PROXY_SETTINGS.DYNAMIC_SIDECAR_ENVOY_CPU_LIMIT
        ram += egress_proxy_count * int(settings.DY_SIDECAR_EGRESS_PROXY_SETTINGS.DYNAMIC_SIDECAR_ENVOY_MEMORY_LIMIT)

    if with_tracing:
        t = settings.DYNAMIC_SIDECAR_USER_SERVICES_TRACING_CONFIG
        # collector + forwarder share the same CPU/RAM settings
        cpu += 2 * t.USER_SERVICES_TRACING_COLLECTOR_CPU_LIMIT
        ram += 2 * int(t.USER_SERVICES_TRACING_COLLECTOR_MEMORY_LIMIT)

    if with_rclone:
        m = settings.DY_SIDECAR_R_CLONE_SETTINGS.R_CLONE_SIMCORE_SDK_MOUNT_SETTINGS
        cpu += m.R_CLONE_SIMCORE_SDK_MOUNT_CONTAINER_NANO_CPUS / 1e9
        ram += int(m.R_CLONE_SIMCORE_SDK_MOUNT_CONTAINER_MEMORY_LIMIT)

    return _Resources(cpu=cpu, ram=ram)


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
) -> None:
    """Subtracts the combined helper-container footprint from the single biggest user service.

    Identifies user services by the presence of ``SIMCORE_NANO_CPUS_LIMIT`` in their
    environment (injected by director-v2) — no image names or service-name patterns needed.

    Mutates ``parsed_compose_spec`` in-place.

    Raises:
        NotEnoughResourcesForExtraContainersError: if the remaining allocation would be
            <= 0 or < 48 % of the service's original CPU or RAM limit.
    """
    spec_services = parsed_compose_spec["services"]
    user_service_names = [name for name, spec in spec_services.items() if _is_user_service(spec)]
    if not user_service_names:
        return

    spec_services = parsed_compose_spec["services"]
    biggest = _find_biggest_overall_service(spec_services, user_service_names)
    original = _read_limits(spec_services[biggest])

    remaining = _Resources(
        cpu=original.cpu - extra.cpu,
        ram=original.ram - extra.ram,
    )

    hard_fail = remaining.cpu <= 0 or remaining.ram <= 0
    soft_fail = (
        remaining.cpu < original.cpu * _MIN_REMAINING_FRACTION or remaining.ram < original.ram * _MIN_REMAINING_FRACTION
    )

    if hard_fail or soft_fail:
        raise NotEnoughResourcesForExtraContainersError(
            service_name=biggest,
            extra_cpu=extra.cpu,
            extra_ram=extra.ram,
            remaining_cpu=remaining.cpu,
            remaining_ram=remaining.ram,
            original_cpu=original.cpu,
            original_ram=original.ram,
            min_fraction=_MIN_REMAINING_FRACTION,
        )

    _write_limits(spec_services[biggest], remaining)
