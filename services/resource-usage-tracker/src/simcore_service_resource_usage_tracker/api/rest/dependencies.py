# mypy: disable-error-code=truthy-function
#
# DEPENDENCIES
#

import logging
from collections.abc import AsyncGenerator, Callable
from typing import Annotated

from fastapi import Depends
from fastapi.requests import Request
from servicelib.fastapi.dependencies import get_app, get_reverse_url_mapper
from sqlalchemy.ext.asyncio import AsyncEngine

from ...services.modules.db.repositories._base import BaseRepository

logger = logging.getLogger(__name__)


def get_resource_tracker_db_engine(request: Request) -> AsyncEngine:
    engine: AsyncEngine = request.app.state.engine
    assert engine  # nosec
    return engine


def get_repository(repo_type: type[BaseRepository]) -> Callable:
    async def _get_repo(
        engine: Annotated[AsyncEngine, Depends(get_resource_tracker_db_engine)],
    ) -> AsyncGenerator[BaseRepository, None]:
        yield repo_type(db_engine=engine)

    return _get_repo


assert get_reverse_url_mapper  # nosec
assert get_app  # nosec

__all__: tuple[str, ...] = (
    "get_app",
    "get_reverse_url_mapper",
)
