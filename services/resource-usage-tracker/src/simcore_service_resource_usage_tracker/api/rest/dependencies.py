# mypy: disable-error-code=truthy-function
#
# DEPENDENCIES
#

import logging

from fastapi.requests import Request
from servicelib.fastapi.dependencies import get_app, get_reverse_url_mapper
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


def get_resource_tracker_db_engine(request: Request) -> AsyncEngine:
    engine: AsyncEngine = request.app.state.engine
    assert engine  # nosec
    return engine


assert get_reverse_url_mapper  # nosec
assert get_app  # nosec

__all__: tuple[str, ...] = (
    "get_app",
    "get_reverse_url_mapper",
)
