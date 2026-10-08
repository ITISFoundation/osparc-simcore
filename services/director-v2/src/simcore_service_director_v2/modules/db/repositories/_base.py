import logging
import math
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine

_logger = logging.getLogger(__name__)

_POOL_UTILIZATION_WARNING_RATIO = 0.9


def _pool_capacity_metrics(engine: AsyncEngine) -> tuple[int, int, int, float] | None:
    """Returns (in_use, warning_threshold, total_capacity, utilization),
    or None when the pool cannot be introspected.
    """
    try:
        in_use = engine.pool.checkedout()  # type: ignore # connections in use
        pool_size = engine.pool.size()  # type: ignore # configured pool size
        max_overflow = max(int(getattr(engine.pool, "_max_overflow", 0)), 0)
    except (TypeError, ValueError):
        # e.g. a mocked engine without a real SQLAlchemy pool
        return None

    total_capacity = pool_size + max_overflow
    warning_threshold = math.ceil(total_capacity * _POOL_UTILIZATION_WARNING_RATIO)
    utilization = in_use / total_capacity if total_capacity > 0 else 0.0
    return in_use, warning_threshold, total_capacity, utilization


@dataclass
class BaseRepository:
    db_engine: AsyncEngine

    def __post_init__(self) -> None:
        if (metrics := _pool_capacity_metrics(self.db_engine)) is None:
            return
        in_use, warning_threshold, total_capacity, utilization = metrics
        if total_capacity > 0 and in_use >= warning_threshold:
            _logger.warning(
                "Database connection pool near limits: checked_out=%s threshold=%s total_capacity=%s "
                "utilization=%.1f%% status=%s",
                in_use,
                warning_threshold,
                total_capacity,
                utilization * 100,
                self.db_engine.pool.status(),
            )
