from dataclasses import dataclass, field
from typing import Final

from prometheus_client import Counter, Histogram
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from servicelib.instrumentation import MetricsBase, get_metrics_namespace

from ..._meta import APP_NAME

_METRICS_NAMESPACE: Final[str] = get_metrics_namespace(APP_NAME)


@dataclass(slots=True, kw_only=True)
class PSchedulerMetrics(SingletonInAppStateMixin, MetricsBase):
    app_state_name = "p_scheduler_metrics_manager"

    reconciliation_duration: Histogram = field(init=False)
    reconciliation_failures: Counter = field(init=False)
    worker_failures: Counter = field(init=False)
    dropped_reconciliation_requests: Counter = field(init=False)
    dropped_worker_requests: Counter = field(init=False)

    def __post_init__(self) -> None:
        self.reconciliation_duration = Histogram(
            "reconciliation_duration_seconds",
            "Duration of a single reconciliation cycle",
            namespace=_METRICS_NAMESPACE,
            subsystem=self.subsystem,
            registry=self.registry,
        )

        self.reconciliation_failures = Counter(
            "reconciliation_failures_total",
            "Number of reconciliation cycles that failed with an exception",
            namespace=_METRICS_NAMESPACE,
            subsystem=self.subsystem,
            registry=self.registry,
        )

        self.worker_failures = Counter(
            "worker_failures_total",
            "Number of worker step executions that failed with an exception",
            namespace=_METRICS_NAMESPACE,
            subsystem=self.subsystem,
            registry=self.registry,
        )

        self.dropped_reconciliation_requests = Counter(
            "dropped_reconciliation_requests_total",
            "Number of reconciliation requests dropped because the queue was full",
            namespace=_METRICS_NAMESPACE,
            subsystem=self.subsystem,
            registry=self.registry,
        )

        self.dropped_worker_requests = Counter(
            "dropped_worker_requests_total",
            "Number of worker requests dropped because the queue was full",
            namespace=_METRICS_NAMESPACE,
            subsystem=self.subsystem,
            registry=self.registry,
        )

    def duration_of_reconciliation(self, duration: float) -> None:
        self.reconciliation_duration.observe(duration)

    def inc_reconciliation_failures(self) -> None:
        self.reconciliation_failures.inc()

    def inc_worker_failures(self) -> None:
        self.worker_failures.inc()

    def inc_dropped_reconciliation_requests(self) -> None:
        self.dropped_reconciliation_requests.inc()

    def inc_dropped_worker_requests(self) -> None:
        self.dropped_worker_requests.inc()
