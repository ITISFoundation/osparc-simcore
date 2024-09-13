from dataclasses import dataclass, field
from typing import Final

from prometheus_client import CollectorRegistry, Histogram
from pydantic import ByteSize, parse_obj_as
from servicelib.instrumentation import get_metrics_namespace

from ...meta import PROJECT_NAME

_NAMESPACE_METRICS: Final[str] = get_metrics_namespace(PROJECT_NAME)
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
    pull_user_services_images_duration: Histogram = field(init=False)

    # ingress rates
    output_ports_pull_rate: Histogram = field(init=False)
    input_ports_pull_rate: Histogram = field(init=False)
    pull_service_state_rate: Histogram = field(init=False)

    # egress rates
    # NOTE: input ports are never pushed
    # NOTE: output ports are pushed by the dy-sidecar, upon change making recovering the metric very complicated
    push_service_state_rate: Histogram = field(init=False)

    def __post_init__(self) -> None:
        self.start_time_duration = Histogram(
            "start_time_duration_seconds",
            "time to start dynamic-sidecar",
            labelnames=_INSTRUMENTATION_LABELS,
            namespace=_NAMESPACE_METRICS,
            buckets=_BUCKETS_TIME_S,
            subsystem=_SUBSYSTEM_NAME,
        )
        self.stop_time_duration = Histogram(
            "stop_time_duration_seconds",
            "time to stop dynamic-sidecar",
            labelnames=_INSTRUMENTATION_LABELS,
            namespace=_NAMESPACE_METRICS,
            buckets=_BUCKETS_TIME_S,
            subsystem=_SUBSYSTEM_NAME,
        )
        self.pull_user_services_images_duration = Histogram(
            "pull_user_services_images_duration_seconds",
            "time to pull docker images",
            labelnames=_INSTRUMENTATION_LABELS,
            namespace=_NAMESPACE_METRICS,
            buckets=_BUCKETS_RATE_BPS,
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
        self.pull_service_state_rate = Histogram(
            "pull_service_state_rate_bps",
            "rate at which service states were recovered",
            labelnames=_INSTRUMENTATION_LABELS,
            namespace=_NAMESPACE_METRICS,
            buckets=_BUCKETS_RATE_BPS,
            subsystem=_SUBSYSTEM_NAME,
        )

        self.push_service_state_rate = Histogram(
            "push_service_state_rate_bps",
            "rate at which service states were saved",
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
