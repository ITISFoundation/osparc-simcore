import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import State
from servicelib.fastapi.postgres_lifespan import PostgresLifespanStateKeys

from .repositories.products import ProductsRepository

_logger = logging.getLogger(__name__)


async def setup_database(app: FastAPI, state: State) -> AsyncIterator[State]:
    app.state.engine = state[PostgresLifespanStateKeys.POSTGRES_ASYNC_ENGINE]

    repo = ProductsRepository(db_engine=app.state.engine)

    app.state.default_product_name = await repo.get_default_product_name()

    yield {}
