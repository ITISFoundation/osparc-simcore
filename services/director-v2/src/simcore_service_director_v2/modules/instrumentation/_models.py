from dataclasses import dataclass, field
from typing import Final

from prometheus_client import CollectorRegistry, Histogram
from prometheus_client.utils import INF

from ...meta import PROJECT_NAME

_MINUTE: Final[int] = 60

_NAMESPACE_METRICS: Final[str] = PROJECT_NAME.replace("-", "_")
_TIME_BUCKETS: Final[tuple[float, ...]] = (
    # all seconds in a minute
    *(x for x in range(60)),
    # all minutes in an hour
    *(x * _MINUTE for x in range(1, 60)),
    INF,
)

_SUBSYSTEM_DYNAMIC_SIDECAR: Final[str] = "dynamic_sidecar"

_START_STOP_LABELS: Final[tuple[str, ...]] = (
    "user_id",
    "wallet_id",
    "service_key",
    "service_version",
)

_SIZE_TIME_LABLES: Final[tuple[str, ...]] = ("byte_size",)


@dataclass(slots=True, kw_only=True)
class DynamiSidecarMetrics:

    start_time_seconds: Histogram = field(init=False)
    stop_time_seconds: Histogram = field(init=False)

    output_ports_pull_seconds: Histogram = field(init=False)
    input_ports_pull_seconds: Histogram = field(init=False)
    pull_user_services_images_seconds: Histogram = field(init=False)

    def __post_init__(self) -> None:
        self.start_time_seconds = Histogram(
            "start_time_duration_seconds",
            "Time taken for dynamic-sidecar to start",
            labelnames=_START_STOP_LABELS,
            namespace=_NAMESPACE_METRICS,
            buckets=_TIME_BUCKETS,
            subsystem=_SUBSYSTEM_DYNAMIC_SIDECAR,
        )
        self.stop_time_seconds = Histogram(
            "stop_time_duration_seconds",
            "Time taken for dynamic-sidecar to stop",
            labelnames=_START_STOP_LABELS,
            namespace=_NAMESPACE_METRICS,
            buckets=_TIME_BUCKETS,
            subsystem=_SUBSYSTEM_DYNAMIC_SIDECAR,
        )

        self.output_ports_pull_seconds = Histogram(
            "output_ports_pull_duration_seconds",
            "time used to pull output ports",
            labelnames=_SIZE_TIME_LABLES,
            namespace=_NAMESPACE_METRICS,
            buckets=_TIME_BUCKETS,
            subsystem=_SUBSYSTEM_DYNAMIC_SIDECAR,
        )
        self.input_ports_pull_seconds = Histogram(
            "input_ports_pull_duration_seconds",
            "time used to pull input ports",
            labelnames=_SIZE_TIME_LABLES,
            namespace=_NAMESPACE_METRICS,
            buckets=_TIME_BUCKETS,
            subsystem=_SUBSYSTEM_DYNAMIC_SIDECAR,
        )
        self.pull_user_services_images_seconds = Histogram(
            "pull_user_services_images_duration_seconds",
            "time used to pull user services docker images",
            labelnames=_SIZE_TIME_LABLES,
            namespace=_NAMESPACE_METRICS,
            buckets=_TIME_BUCKETS,
            subsystem=_SUBSYSTEM_DYNAMIC_SIDECAR,
        )


@dataclass(slots=True, kw_only=True)
class DirectorV2Instrumentation:
    registry: CollectorRegistry

    dynamic_sidecar_metrics: DynamiSidecarMetrics = field(init=False)

    def __post_init__(self) -> None:
        self.dynamic_sidecar_metrics = DynamiSidecarMetrics()
