from dataclasses import dataclass, field
from typing import Final

from prometheus_client import CollectorRegistry, Histogram
from pydantic import ByteSize, parse_obj_as

from ...meta import PROJECT_NAME

_NAMESPACE_METRICS: Final[str] = PROJECT_NAME.replace("-", "_")
_SUBSYSTEM_NAME: Final[str] = "dynamic_services"
_INSTRUMENTATION_LABELS: Final[tuple[str, ...]] = (
    "user_id",
    "wallet_id",
    "service_key",
    "service_version",
)

_MINUTE: Final[int] = 60
_BUCKETS_TIME_S: Final[tuple[float, ...]] = (
    10,
    30,
    1 * _MINUTE,
    2 * _MINUTE,
    3 * _MINUTE,
    5 * _MINUTE,
    7 * _MINUTE,
    10 * _MINUTE,
    15 * _MINUTE,
    20 * _MINUTE,
)


_BUCKETS_RATE_BPS: Final[tuple[float, ...]] = tuple(
    parse_obj_as(ByteSize, f"{m}MiB")
    for m in (
        1,
        30,
        60,
        90,
        120,
        150,
        200,
        300,
        400,
        500,
        600,
    )
)


@dataclass(slots=True, kw_only=True)
class DynamiSidecarMetrics:

    start_time_duration: Histogram = field(init=False)
    stop_time_duration: Histogram = field(init=False)

    output_ports_pull_rate: Histogram = field(init=False)
    input_ports_pull_rate: Histogram = field(init=False)
    pull_user_services_images_rate: Histogram = field(init=False)
    recover_service_state_rate: Histogram = field(init=False)

    def __post_init__(self) -> None:
        self.start_time_duration = Histogram(
            "start_time_duration_seconds",
            "Time taken for dynamic-sidecar to start",
            labelnames=_INSTRUMENTATION_LABELS,
            namespace=_NAMESPACE_METRICS,
            buckets=_BUCKETS_TIME_S,
            subsystem=_SUBSYSTEM_NAME,
        )
        self.stop_time_duration = Histogram(
            "stop_time_duration_seconds",
            "Time taken for dynamic-sidecar to stop",
            labelnames=_INSTRUMENTATION_LABELS,
            namespace=_NAMESPACE_METRICS,
            buckets=_BUCKETS_TIME_S,
            subsystem=_SUBSYSTEM_NAME,
        )

        self.output_ports_pull_rate = Histogram(
            "output_ports_pull_rate_bps",
            "rate at which output ports were pulled",
            labelnames=_INSTRUMENTATION_LABELS,
            namespace=_NAMESPACE_METRICS,
            buckets=_BUCKETS_RATE_BPS,
            subsystem=_SUBSYSTEM_NAME,
        )
        self.input_ports_pull_rate = Histogram(
            "input_ports_pull_rate_bps",
            "rate at which input ports were pulled",
            labelnames=_INSTRUMENTATION_LABELS,
            namespace=_NAMESPACE_METRICS,
            buckets=_BUCKETS_RATE_BPS,
            subsystem=_SUBSYSTEM_NAME,
        )
        self.pull_user_services_images_rate = Histogram(
            "pull_user_services_images_rate_bps",
            "rate at which user services were pulled",
            labelnames=_INSTRUMENTATION_LABELS,
            namespace=_NAMESPACE_METRICS,
            buckets=_BUCKETS_RATE_BPS,
            subsystem=_SUBSYSTEM_NAME,
        )
        self.recover_service_state_rate = Histogram(
            "restore_service_state_rate_bps",
            "rate at which service states were recovered",
            labelnames=_INSTRUMENTATION_LABELS,
            namespace=_NAMESPACE_METRICS,
            buckets=_BUCKETS_RATE_BPS,
            subsystem=_SUBSYSTEM_NAME,
        )


@dataclass(slots=True, kw_only=True)
class DirectorV2Instrumentation:
    registry: CollectorRegistry

    dynamic_sidecar_metrics: DynamiSidecarMetrics = field(init=False)

    def __post_init__(self) -> None:
        self.dynamic_sidecar_metrics = DynamiSidecarMetrics()
