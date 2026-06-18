"""Prometheus metrics for SQLAlchemy AsyncEngine connection pool evolution."""

import logging
from dataclasses import dataclass, field

from prometheus_client import Counter, Gauge
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine

from servicelib.logging_utils import log_context

from .instrumentation import MetricsBase

_logger = logging.getLogger(__name__)

_HIGH_UTILIZATION_THRESHOLD: float = 0.9


@dataclass(slots=True, kw_only=True)
class DbPoolMetrics(MetricsBase):
    """Prometheus metrics tracking SQLAlchemy connection pool evolution.

    Exposes instantaneous pool state as Gauges plus a Counter that increments
    every time pool utilization is sampled at or above the high-utilization
    threshold (90 % of total capacity).

    Metric names follow the pattern:
        {namespace}_{subsystem}_pool_connections_checked_out
        {namespace}_{subsystem}_pool_connections_size
        {namespace}_{subsystem}_pool_connections_overflow
        {namespace}_{subsystem}_pool_connections_total_capacity
        {namespace}_{subsystem}_pool_utilization_ratio
        {namespace}_{subsystem}_pool_high_utilization_total
    """

    namespace: str

    pool_connections_checked_out: Gauge = field(init=False)
    pool_connections_size: Gauge = field(init=False)
    pool_connections_overflow: Gauge = field(init=False)
    pool_connections_total_capacity: Gauge = field(init=False)
    pool_utilization_ratio: Gauge = field(init=False)
    pool_high_utilization_total: Counter = field(init=False)

    def __post_init__(self) -> None:
        self.pool_connections_checked_out = Gauge(
            "pool_connections_checked_out",
            "Connections currently checked out from the SQLAlchemy pool",
            namespace=self.namespace,
            subsystem=self.subsystem,
            registry=self.registry,
        )
        self.pool_connections_size = Gauge(
            "pool_connections_size",
            "Configured permanent pool size",
            namespace=self.namespace,
            subsystem=self.subsystem,
            registry=self.registry,
        )
        self.pool_connections_overflow = Gauge(
            "pool_connections_overflow",
            "Overflow connections currently in use beyond the configured pool size",
            namespace=self.namespace,
            subsystem=self.subsystem,
            registry=self.registry,
        )
        self.pool_connections_total_capacity = Gauge(
            "pool_connections_total_capacity",
            "Total connection capacity: pool_size + max_overflow",
            namespace=self.namespace,
            subsystem=self.subsystem,
            registry=self.registry,
        )
        self.pool_utilization_ratio = Gauge(
            "pool_utilization_ratio",
            "Fraction of total pool capacity currently in use [0, 1]",
            namespace=self.namespace,
            subsystem=self.subsystem,
            registry=self.registry,
        )
        self.pool_high_utilization_total = Counter(
            "pool_high_utilization_total",
            f"Number of pool samples where utilization was >= {_HIGH_UTILIZATION_THRESHOLD:.0%}",
            namespace=self.namespace,
            subsystem=self.subsystem,
            registry=self.registry,
        )


def setup_pool_metrics_instrumentation(
    engine: AsyncEngine,
    pool_metrics: DbPoolMetrics,
) -> None:
    """Instruments *engine*'s pool to push Prometheus metrics in real time.

    Attaches SQLAlchemy ``checkout`` and ``checkin`` pool event listeners so
    that gauges are updated the instant a connection is borrowed or returned —
    not on the next Prometheus scrape cycle.

    Static configuration metrics (``pool_connections_size``,
    ``pool_connections_total_capacity``) are written once at call time.

    Silently no-ops if the pool type does not expose the expected attributes
    (e.g. ``NullPool`` used in tests).
    """
    sync_pool = engine.sync_engine.pool

    # Write static configuration metrics once.
    pool_size: int = int(sync_pool.size())  # type: ignore[attr-defined]
    max_overflow: int = max(int(getattr(sync_pool, "_max_overflow", 0)), 0)
    pool_metrics.pool_connections_size.set(pool_size)
    pool_metrics.pool_connections_total_capacity.set(pool_size + max_overflow)

    def _update_dynamic_metrics() -> None:
        try:
            checked_out: int = int(sync_pool.checkedout())  # type: ignore[attr-defined]
            _pool_size: int = int(sync_pool.size())  # type: ignore[attr-defined]
            _max_overflow: int = max(int(getattr(sync_pool, "_max_overflow", 0)), 0)
            total_capacity = _pool_size + _max_overflow
            overflow_in_use = max(checked_out - _pool_size, 0)
            utilization = checked_out / total_capacity if total_capacity > 0 else 0.0

            pool_metrics.pool_connections_checked_out.set(checked_out)
            pool_metrics.pool_connections_overflow.set(overflow_in_use)
            pool_metrics.pool_utilization_ratio.set(utilization)

            if utilization >= _HIGH_UTILIZATION_THRESHOLD:
                pool_metrics.pool_high_utilization_total.inc()
        except AttributeError:
            pass

    # initial metrics update to avoid Prometheus scrape with all zeros
    _update_dynamic_metrics()
    # Attach event listeners to update metrics on every connection checkout/checkin.
    with log_context(_logger, logging.INFO, f"set up pool metrics instrumentation for engine {engine}"):
        event.listen(
            sync_pool,
            "checkout",
            lambda dbapi_conn, conn_record, conn_proxy: _update_dynamic_metrics(),  # noqa: ARG005
        )
        event.listen(
            sync_pool,
            "checkin",
            lambda dbapi_conn, conn_record: _update_dynamic_metrics(),  # noqa: ARG005
        )
