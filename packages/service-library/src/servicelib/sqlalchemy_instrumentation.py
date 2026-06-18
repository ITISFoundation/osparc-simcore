"""SQLAlchemy AsyncEngine instrumentation using OpenTelemetry contrib."""

import logging

from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from sqlalchemy.ext.asyncio import AsyncEngine

from servicelib.logging_utils import log_context

from .tracing import TracingConfig

_logger = logging.getLogger(__name__)


def instrument_async_engine(
    engine: AsyncEngine,
    *,
    tracing_config: TracingConfig | None,
) -> AsyncEngine:
    """Instruments a SQLAlchemy AsyncEngine with OpenTelemetry contrib instrumentation."""
    if tracing_config is None or not tracing_config.tracing_enabled:
        return engine

    assert tracing_config.tracer_provider  # nosec

    sync_engine = engine.sync_engine
    with log_context(_logger, logging.DEBUG, f"Instrumenting {sync_engine} with OpenTelemetry"):
        SQLAlchemyInstrumentor().instrument(
            engine=sync_engine,
            enable_commenter=False,
            tracer_provider=tracing_config.tracer_provider,
        )

    return engine
