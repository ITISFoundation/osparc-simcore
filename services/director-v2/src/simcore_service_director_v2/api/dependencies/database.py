import logging

from fastapi.requests import Request
from sqlalchemy.ext.asyncio import AsyncEngine

_logger = logging.getLogger(__name__)

_POOL_UTILIZATION_WARNING_RATIO = 0.9


def get_db_engine(request: Request) -> AsyncEngine:
    assert request.app.state.engine  # nosec
    engine: AsyncEngine = request.app.state.engine
    return engine
