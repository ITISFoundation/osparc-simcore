import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from sqlalchemy.ext.asyncio import AsyncEngine

from .products import ProductsRepository

_logger = logging.getLogger(__name__)


async def _database_lifespan(app: FastAPI) -> AsyncIterator[State]:
    assert isinstance(app.state.engine, AsyncEngine)  # nosec

    repo = ProductsRepository(db_engine=app.state.engine)

    app.state.default_product_name = await repo.get_default_product_name()

    yield {}


repository_lifespan_manager = LifespanManager()
repository_lifespan_manager.add(_database_lifespan)
