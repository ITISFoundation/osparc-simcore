"""SQLAlchemy AsyncEngine instrumentation using OpenTelemetry contrib."""

import logging

from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from sqlalchemy.ext.asyncio import AsyncEngine

_logger = logging.getLogger(__name__)


def instrument_async_engine(
    engine: AsyncEngine,
) -> AsyncEngine:
    """Instruments a SQLAlchemy AsyncEngine with OpenTelemetry contrib instrumentation."""
    sync_engine = engine.sync_engine

    SQLAlchemyInstrumentor().instrument(
        engine=sync_engine,
        enable_commenter=False,
    )

    return engine
