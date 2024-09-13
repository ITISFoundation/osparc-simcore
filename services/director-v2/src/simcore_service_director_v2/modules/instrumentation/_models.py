from dataclasses import dataclass, field
from typing import Final

from prometheus_client import CollectorRegistry, Histogram
from prometheus_client.utils import INF
from pydantic import ByteSize, parse_obj_as

from ...meta import PROJECT_NAME

_NAMESPACE_METRICS: Final[str] = PROJECT_NAME.replace("-", "_")
_SUBSYSTEM_DYNAMIC_SIDECAR: Final[str] = "dynamic_sidecar"
_INSTRUMENTATION_LABELS: Final[tuple[str, ...]] = (
    "user_id",
    "wallet_id",
    "service_key",
    "service_version",
)

_MINUTE: Final[int] = 60
_TIME_BUCKETS: Final[tuple[float, ...]] = (
    # all seconds in a minute
    *(x for x in range(60)),
    # all minutes in an hour
    *(x * _MINUTE for x in range(1, 60)),
    INF,
)


# 1MiB/s, 30MiB/s, 60MiB/s, 90MiB/s, 120MiB/s, 150MiB/s, 200MiB/s, 300MiB/s, 400MiB/s, 500MiB/s, 600MiB/s
_SPPEDS_MiB_S: tuple[int, ...] = (1, 30, 60, 90, 120, 150, 200, 300, 400, 500, 600)
_BUCKETS_SPPED_RATES: Final[tuple[float, ...]] = tuple(
    parse_obj_as(ByteSize, f"{m}MiB") for m in _SPPEDS_MiB_S
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
            buckets=_TIME_BUCKETS,
            subsystem=_SUBSYSTEM_DYNAMIC_SIDECAR,
        )
        self.stop_time_duration = Histogram(
            "stop_time_duration_seconds",
            "Time taken for dynamic-sidecar to stop",
            labelnames=_INSTRUMENTATION_LABELS,
            namespace=_NAMESPACE_METRICS,
            buckets=_TIME_BUCKETS,
            subsystem=_SUBSYSTEM_DYNAMIC_SIDECAR,
        )

        self.output_ports_pull_rate = Histogram(
            "output_ports_pull_rate_bps",
            "rate at which output ports were pulled",
            labelnames=_INSTRUMENTATION_LABELS,
            namespace=_NAMESPACE_METRICS,
            buckets=_BUCKETS_SPPED_RATES,
            subsystem=_SUBSYSTEM_DYNAMIC_SIDECAR,
        )
        self.input_ports_pull_rate = Histogram(
            "input_ports_pull_rate_bps",
            "rate at which input ports were pulled",
            labelnames=_INSTRUMENTATION_LABELS,
            namespace=_NAMESPACE_METRICS,
            buckets=_BUCKETS_SPPED_RATES,
            subsystem=_SUBSYSTEM_DYNAMIC_SIDECAR,
        )
        self.pull_user_services_images_rate = Histogram(
            "pull_user_services_images_rate_bps",
            "rate at which user services were pulled",
            labelnames=_INSTRUMENTATION_LABELS,
            namespace=_NAMESPACE_METRICS,
            buckets=_BUCKETS_SPPED_RATES,
            subsystem=_SUBSYSTEM_DYNAMIC_SIDECAR,
        )
        self.recover_service_state_rate = Histogram(
            "restore_service_state_rate_bps",
            "rate at which service states were recovered",
            labelnames=_INSTRUMENTATION_LABELS,
            namespace=_NAMESPACE_METRICS,
            buckets=_BUCKETS_SPPED_RATES,
            subsystem=_SUBSYSTEM_DYNAMIC_SIDECAR,
        )


@dataclass(slots=True, kw_only=True)
class DirectorV2Instrumentation:
    registry: CollectorRegistry

    dynamic_sidecar_metrics: DynamiSidecarMetrics = field(init=False)

    def __post_init__(self) -> None:
        self.dynamic_sidecar_metrics = DynamiSidecarMetrics()
