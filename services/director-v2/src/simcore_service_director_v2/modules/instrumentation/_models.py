import collections
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Final

from prometheus_client import CollectorRegistry, Gauge, Histogram
from pydantic import ByteSize, TypeAdapter
from servicelib.db_asyncpg_pool_metrics import DbPoolMetrics
from servicelib.instrumentation import MetricsBase, get_metrics_namespace

from ..._meta import PROJECT_NAME

_METRICS_NAMESPACE: Final[str] = get_metrics_namespace(PROJECT_NAME)
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


_RATE_BPS_BUCKETS: Final[tuple[float, ...]] = tuple(
    TypeAdapter(ByteSize).validate_python(f"{m}MiB")
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
class DynamiSidecarMetrics(MetricsBase):
    running_services_count: Gauge = field(init=False)
    _running_services_seen_labels: set[tuple[str, ...]] = field(init=False, default_factory=set)

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
        self.running_services_count = Gauge(
            "running_services_count",
            "number of dynamic services currently running",
            labelnames=_INSTRUMENTATION_LABELS,
            namespace=_METRICS_NAMESPACE,
            subsystem=self.subsystem,
            registry=self.registry,
        )
        self.start_time_duration = Histogram(
            "start_time_duration_seconds",
            "time to start dynamic service (from start request in dv-2 till service "
            "containers are in running state (healthy))",
            labelnames=_INSTRUMENTATION_LABELS,
            namespace=_METRICS_NAMESPACE,
            buckets=_BUCKETS_TIME_S,
            subsystem=self.subsystem,
            registry=self.registry,
        )
        self.stop_time_duration = Histogram(
            "stop_time_duration_seconds",
            "time to stop dynamic service (from stop request in dv-2 till all allocated resources "
            "(services + dynamic-sidecar) are removed)",
            labelnames=_INSTRUMENTATION_LABELS,
            namespace=_METRICS_NAMESPACE,
            buckets=_BUCKETS_TIME_S,
            subsystem=self.subsystem,
            registry=self.registry,
        )
        self.pull_user_services_images_duration = Histogram(
            "pull_user_services_images_duration_seconds",
            "time to pull docker images",
            labelnames=_INSTRUMENTATION_LABELS,
            namespace=_METRICS_NAMESPACE,
            buckets=_BUCKETS_TIME_S,
            subsystem=self.subsystem,
            registry=self.registry,
        )

        self.output_ports_pull_rate = Histogram(
            "output_ports_pull_rate_bps",
            "rate at which output ports were pulled",
            labelnames=_INSTRUMENTATION_LABELS,
            namespace=_METRICS_NAMESPACE,
            buckets=_RATE_BPS_BUCKETS,
            subsystem=self.subsystem,
            registry=self.registry,
        )
        self.input_ports_pull_rate = Histogram(
            "input_ports_pull_rate_bps",
            "rate at which input ports were pulled",
            labelnames=_INSTRUMENTATION_LABELS,
            namespace=_METRICS_NAMESPACE,
            buckets=_RATE_BPS_BUCKETS,
            subsystem=self.subsystem,
            registry=self.registry,
        )
        self.pull_service_state_rate = Histogram(
            "pull_service_state_rate_bps",
            "rate at which service states were recovered",
            labelnames=_INSTRUMENTATION_LABELS,
            namespace=_METRICS_NAMESPACE,
            buckets=_RATE_BPS_BUCKETS,
            subsystem=self.subsystem,
            registry=self.registry,
        )

        self.push_service_state_rate = Histogram(
            "push_service_state_rate_bps",
            "rate at which service states were saved",
            labelnames=_INSTRUMENTATION_LABELS,
            namespace=_METRICS_NAMESPACE,
            buckets=_RATE_BPS_BUCKETS,
            subsystem=self.subsystem,
            registry=self.registry,
        )

    def update_running_services_count(self, all_labels: Iterable[Mapping[str, str]]) -> None:
        """Recomputes the gauge from the current set of tracked services (self-healing snapshot,
        instead of incremental inc/dec which can drift on crashes/manual-intervention/error paths)."""
        label_tuples = [tuple(labels[name] for name in _INSTRUMENTATION_LABELS) for labels in all_labels]
        counts = collections.Counter(label_tuples)
        current_labels = set(counts)
        for label_tuple, count in counts.items():
            self.running_services_count.labels(*label_tuple).set(count)
        # drop combinations no longer present, instead of leaving zeroed series forever
        for label_tuple in self._running_services_seen_labels - current_labels:
            self.running_services_count.remove(*label_tuple)
        self._running_services_seen_labels = current_labels


@dataclass(slots=True, kw_only=True)
class DirectorV2Instrumentation:
    registry: CollectorRegistry
    dynamic_sidecar_metrics: DynamiSidecarMetrics = field(init=False)
    db_pool_metrics: DbPoolMetrics = field(init=False)

    def __post_init__(self) -> None:
        self.dynamic_sidecar_metrics = DynamiSidecarMetrics(  # pylint: disable=unexpected-keyword-arg
            subsystem="dynamic_services", registry=self.registry
        )
        self.db_pool_metrics = DbPoolMetrics(
            subsystem="database",
            namespace=_METRICS_NAMESPACE,
            registry=self.registry,
        )
