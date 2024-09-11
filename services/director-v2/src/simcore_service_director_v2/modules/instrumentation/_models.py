from dataclasses import dataclass, field
from typing import Final

from prometheus_client import CollectorRegistry, Histogram
from prometheus_client.utils import INF

from ...meta import PROJECT_NAME

_MINUTE: Final[int] = 60

_NAMESPACE_METRICS: Final[str] = PROJECT_NAME.replace("-", "_")
_TIMING_BUCKETS: Final[tuple[float, ...]] = (
    # all seconds in a minute
    *(x for x in range(60)),
    # all minutes in an hour
    *(x * _MINUTE for x in range(1, 60)),
    INF,
)

_SUBSYSTEM_DYNAMIC_SIDECAR: Final[str] = "dynamic_sidecar"


@dataclass(slots=True, kw_only=True)
class DynamiSidecarMetrics:

    # TODO: add a test for hystograms here
    dy_sidecar_start_time_seconds: Histogram = field(init=False)

    def __post_init__(self) -> None:
        self.dy_sidecar_start_time_seconds = Histogram(
            "dy_sidecar_start_time_duration_seconds",
            "Time taken for dynamic-sde",
            namespace=_NAMESPACE_METRICS,
            buckets=_TIMING_BUCKETS,
            subsystem=_SUBSYSTEM_DYNAMIC_SIDECAR,
        )


@dataclass(slots=True, kw_only=True)
class DirectorV2Instrumentation:
    registry: CollectorRegistry

    dynamic_sidecar_metrics: DynamiSidecarMetrics = field(init=False)

    def __post_init__(self) -> None:
        self.dynamic_sidecar_metrics = DynamiSidecarMetrics()
